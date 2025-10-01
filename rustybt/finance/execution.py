#
# Copyright 2014 Quantopian, Inc.
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

import abc
from sys import float_info

from numpy import isfinite

import rustybt.utils.math_utils as zp_math
from rustybt.errors import BadOrderParameters
from rustybt.utils.compat import consistent_round


class ExecutionStyle(metaclass=abc.ABCMeta):
    """Base class for order execution styles."""

    _exchange = None

    @abc.abstractmethod
    def get_limit_price(self, is_buy):
        """
        Get the limit price for this order.
        Returns either None or a numerical value >= 0.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_stop_price(self, is_buy):
        """
        Get the stop price for this order.
        Returns either None or a numerical value >= 0.
        """
        raise NotImplementedError

    @property
    def exchange(self):
        """
        The exchange to which this order should be routed.
        """
        return self._exchange


class MarketOrder(ExecutionStyle):
    """
    Execution style for orders to be filled at current market price.

    This is the default for orders placed with :func:`~zipline.api.order`.
    """

    def __init__(self, exchange=None):
        self._exchange = exchange

    def get_limit_price(self, _is_buy):
        return None

    def get_stop_price(self, _is_buy):
        return None


class LimitOrder(ExecutionStyle):
    """
    Execution style for orders to be filled at a price equal to or better than
    a specified limit price.

    Parameters
    ----------
    limit_price : float
        Maximum price for buys, or minimum price for sells, at which the order
        should be filled.
    """

    def __init__(self, limit_price, asset=None, exchange=None):
        check_stoplimit_prices(limit_price, "limit")

        self.limit_price = limit_price
        self._exchange = exchange
        self.asset = asset

    def get_limit_price(self, is_buy):
        return asymmetric_round_price(
            self.limit_price,
            is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )

    def get_stop_price(self, _is_buy):
        return None


class StopOrder(ExecutionStyle):
    """
    Execution style representing a market order to be placed if market price
    reaches a threshold.

    Parameters
    ----------
    stop_price : float
        Price threshold at which the order should be placed. For sells, the
        order will be placed if market price falls below this value. For buys,
        the order will be placed if market price rises above this value.
    """

    def __init__(self, stop_price, asset=None, exchange=None):
        check_stoplimit_prices(stop_price, "stop")

        self.stop_price = stop_price
        self._exchange = exchange
        self.asset = asset

    def get_limit_price(self, _is_buy):
        return None

    def get_stop_price(self, is_buy):
        return asymmetric_round_price(
            self.stop_price,
            not is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )


class StopLimitOrder(ExecutionStyle):
    """
    Execution style representing a limit order to be placed if market price
    reaches a threshold.

    Parameters
    ----------
    limit_price : float
        Maximum price for buys, or minimum price for sells, at which the order
        should be filled, if placed.
    stop_price : float
        Price threshold at which the order should be placed. For sells, the
        order will be placed if market price falls below this value. For buys,
        the order will be placed if market price rises above this value.
    """

    def __init__(self, limit_price, stop_price, asset=None, exchange=None):
        check_stoplimit_prices(limit_price, "limit")
        check_stoplimit_prices(stop_price, "stop")

        self.limit_price = limit_price
        self.stop_price = stop_price
        self._exchange = exchange
        self.asset = asset

    def get_limit_price(self, is_buy):
        return asymmetric_round_price(
            self.limit_price,
            is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )

    def get_stop_price(self, is_buy):
        return asymmetric_round_price(
            self.stop_price,
            not is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )


def asymmetric_round_price(price, prefer_round_down, tick_size, diff=0.95):
    """
    Asymmetric rounding function for adjusting prices to the specified number
    of places in a way that "improves" the price. For limit prices, this means
    preferring to round down on buys and preferring to round up on sells.
    For stop prices, it means the reverse.

    If prefer_round_down == True:
        When .05 below to .95 above a specified decimal place, use it.
    If prefer_round_down == False:
        When .95 below to .05 above a specified decimal place, use it.

    In math-speak:
    If prefer_round_down: [<X-1>.0095, X.0195) -> round to X.01.
    If not prefer_round_down: (<X-1>.0005, X.0105] -> round to X.01.
    """
    precision = zp_math.number_of_decimal_places(tick_size)
    multiplier = int(tick_size * (10**precision))
    diff -= 0.5  # shift the difference down
    diff *= 10**-precision  # adjust diff to precision of tick size
    diff *= multiplier  # adjust diff to value of tick_size

    # Subtracting an epsilon from diff to enforce the open-ness of the upper
    # bound on buys and the lower bound on sells.  Using the actual system
    # epsilon doesn't quite get there, so use a slightly less epsilon-ey value.
    epsilon = float_info.epsilon * 10
    diff = diff - epsilon

    # relies on rounding half away from zero, unlike numpy's bankers' rounding
    rounded = tick_size * consistent_round(
        (price - (diff if prefer_round_down else -diff)) / tick_size
    )
    if zp_math.tolerant_equals(rounded, 0.0):
        return 0.0
    return rounded


class TrailingStopOrder(ExecutionStyle):
    """
    Execution style for trailing stop orders that adjust stop price as market
    price moves favorably.

    Parameters
    ----------
    trail_amount : float, optional
        Absolute dollar amount to trail behind market price.
    trail_percent : float, optional
        Percentage (as decimal) to trail behind market price.
        For example, 0.05 = 5% trailing stop.

    Notes:
    -----
    Exactly one of trail_amount or trail_percent must be specified.
    For long positions: stop_price = highest_price - trail_amount (or * trail_percent)
    For short positions: stop_price = lowest_price + trail_amount (or * trail_percent)
    """

    def __init__(self, trail_amount=None, trail_percent=None, asset=None, exchange=None):
        if trail_amount is None and trail_percent is None:
            raise BadOrderParameters(
                msg="TrailingStopOrder requires either trail_amount or trail_percent"
            )
        if trail_amount is not None and trail_percent is not None:
            raise BadOrderParameters(
                msg="TrailingStopOrder cannot have both trail_amount and trail_percent"
            )

        if trail_amount is not None:
            if trail_amount <= 0:
                raise BadOrderParameters(
                    msg=f"trail_amount must be positive, got {trail_amount}"
                )
            self.trail_amount = trail_amount
            self.trail_percent = None
        else:
            if trail_percent <= 0 or trail_percent >= 1:
                raise BadOrderParameters(
                    msg=f"trail_percent must be between 0 and 1, got {trail_percent}"
                )
            self.trail_amount = None
            self.trail_percent = trail_percent

        self._exchange = exchange
        self.asset = asset
        # Internal tracking for trailing stop adjustment
        self._highest_price = None
        self._lowest_price = None
        self._stop_price = None

    def update_trailing_stop(self, current_price, is_buy):
        """Update the trailing stop price based on current market price.

        Parameters
        ----------
        current_price : float
            Current market price
        is_buy : bool
            True if this is a buy order (closing short), False if sell (closing long)

        Returns:
        -------
        float
            Updated stop price
        """
        if is_buy:
            # For buy/cover orders (closing short), track lowest price
            if self._lowest_price is None or current_price < self._lowest_price:
                self._lowest_price = current_price

            if self.trail_amount is not None:
                self._stop_price = self._lowest_price + self.trail_amount
            else:
                self._stop_price = self._lowest_price * (1 + self.trail_percent)
        else:
            # For sell orders (closing long), track highest price
            if self._highest_price is None or current_price > self._highest_price:
                self._highest_price = current_price

            if self.trail_amount is not None:
                self._stop_price = self._highest_price - self.trail_amount
            else:
                self._stop_price = self._highest_price * (1 - self.trail_percent)

        return self._stop_price

    def get_limit_price(self, _is_buy):
        return None

    def get_stop_price(self, is_buy):
        if self._stop_price is None:
            return None
        return asymmetric_round_price(
            self._stop_price,
            not is_buy,
            tick_size=(0.01 if self.asset is None else self.asset.tick_size),
        )


class OCOOrder(ExecutionStyle):
    """
    One-Cancels-Other (OCO) order execution style.

    Links two orders together such that when one fills, the other is automatically
    canceled. Commonly used for take-profit/stop-loss pairs.

    Parameters
    ----------
    order1_style : ExecutionStyle
        First order's execution style
    order2_style : ExecutionStyle
        Second order's execution style

    Notes:
    -----
    Both orders must be for the same asset and typically opposite directions
    (e.g., one limit order above market, one stop order below market).
    """

    def __init__(self, order1_style, order2_style, exchange=None):
        if not isinstance(order1_style, ExecutionStyle):
            raise BadOrderParameters(
                msg="order1_style must be an ExecutionStyle instance"
            )
        if not isinstance(order2_style, ExecutionStyle):
            raise BadOrderParameters(
                msg="order2_style must be an ExecutionStyle instance"
            )

        self.order1_style = order1_style
        self.order2_style = order2_style
        self._exchange = exchange
        # Track which order filled first
        self._filled_order = None

    def get_limit_price(self, _is_buy):
        # OCO doesn't have its own limit price; child orders have prices
        return None

    def get_stop_price(self, _is_buy):
        # OCO doesn't have its own stop price; child orders have prices
        return None


class BracketOrder(ExecutionStyle):
    """
    Bracket order execution style combining entry, stop-loss, and take-profit.

    A bracket order consists of three parts:
    1. Entry order (limit or market)
    2. Stop-loss order (activated after entry fills)
    3. Take-profit order (activated after entry fills)

    The stop-loss and take-profit orders form an OCO pair.

    Parameters
    ----------
    entry_style : ExecutionStyle
        Execution style for the entry order
    stop_loss_price : float
        Stop price for the protective stop-loss order
    take_profit_price : float
        Limit price for the take-profit order

    Notes:
    -----
    After entry fills, stop-loss and take-profit orders are automatically placed
    as an OCO pair. When one fills, the other is canceled.
    """

    def __init__(
        self,
        entry_style,
        stop_loss_price,
        take_profit_price,
        asset=None,
        exchange=None
    ):
        if not isinstance(entry_style, ExecutionStyle):
            raise BadOrderParameters(
                msg="entry_style must be an ExecutionStyle instance"
            )

        check_stoplimit_prices(stop_loss_price, "stop_loss")
        check_stoplimit_prices(take_profit_price, "take_profit")

        self.entry_style = entry_style
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self._exchange = exchange
        self.asset = asset
        # Track bracket state
        self._entry_filled = False
        self._stop_loss_order_id = None
        self._take_profit_order_id = None

    def get_limit_price(self, is_buy):
        # Return entry order's limit price
        return self.entry_style.get_limit_price(is_buy)

    def get_stop_price(self, is_buy):
        # Return entry order's stop price
        return self.entry_style.get_stop_price(is_buy)


def check_stoplimit_prices(price, label):
    """
    Check to make sure the stop/limit prices are reasonable and raise
    a BadOrderParameters exception if not.
    """
    try:
        if not isfinite(price):
            raise BadOrderParameters(
                msg=f"Attempted to place an order with a {label} price "
                f"of {price}."
            )
    # This catches arbitrary objects
    except TypeError as exc:
        raise BadOrderParameters(
            msg=f"Attempted to place an order with a {label} price "
            f"of {type(price)}."
        ) from exc

    if price < 0:
        raise BadOrderParameters(
            msg=f"Can't place a {label} order with a negative price."
        )
