"""Trading and account control mechanisms for risk management.

This module provides control mechanisms that act as fail-safes to prevent
undesirable trading behavior in algorithms. Controls are checked before
orders are placed (TradingControl) or during algorithm execution
(AccountControl).

Trading Controls:
    - TradingControl: Abstract base for order-level controls
    - MaxOrderCount: Limit number of orders per day
    - RestrictedListOrder: Prevent trading in restricted assets
    - MaxOrderSize: Limit order size by shares or notional value
    - MaxPositionSize: Limit maximum position size
    - LongOnly: Prevent short positions
    - AssetDateBounds: Enforce asset trading date boundaries

Account Controls:
    - AccountControl: Abstract base for account-level controls
    - MaxLeverage: Limit maximum account leverage
    - MinLeverage: Enforce minimum leverage after a deadline

Examples:
    Setting up trading controls::

        from rustybt.finance.controls import MaxOrderCount, LongOnly
        from rustybt.api import set_max_order_count, set_long_only

        def initialize(context):
            # Limit to 100 orders per day
            set_max_order_count(100)
            # Prevent short selling
            set_long_only()

    Setting up account controls::

        from rustybt.finance.controls import MaxLeverage
        from rustybt.api import set_max_leverage

        def initialize(context):
            # Limit leverage to 2x
            set_max_leverage(2.0)
"""
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
import logging
from datetime import datetime

from rustybt.errors import (
    AccountControlViolation,
    TradingControlViolation,
)
from rustybt.utils.input_validation import (
    expect_bounded,
    expect_types,
)

log = logging.getLogger("TradingControl")


class TradingControl(metaclass=abc.ABCMeta):
    """Abstract base class for trading controls that prevent undesirable orders.

    Trading controls are fail-safe mechanisms that validate orders before they
    are placed. Each control validates that an order doesn't violate specific
    constraints (e.g., maximum order size, restricted assets, etc.).

    Controls can be configured to either raise an exception or log a warning
    when violations occur, based on the on_error parameter.

    Attributes:
        on_error: How to handle violations ("fail" to raise exception, "log" to warn).
        _TradingControl__fail_args: Arguments to include in error messages.

    Examples:
        >>> from rustybt.finance.controls import MaxOrderCount
        >>> control = MaxOrderCount(on_error="fail", max_count=100)
        >>> # During backtesting, control.validate() is called before each order
    """

    def __init__(self, on_error, **kwargs):
        """Initialize trading control.

        Args:
            on_error: How to handle violations. Options:
                - "fail": Raise TradingControlViolation exception
                - "log": Log warning but allow order
            **kwargs: Additional arguments to display in error messages.
        """
        self.on_error = on_error
        self.__fail_args = kwargs

    @abc.abstractmethod
    def validate(self, asset, amount, portfolio, algo_datetime, algo_current_data):
        """Validate that an order doesn't violate this control's constraint.

        This method is called exactly once per registered TradingControl before
        each order is placed. If the order passes validation, it should return
        None with no side effects. If the order violates the constraint, it
        should call handle_violation().

        Args:
            asset: The asset being ordered.
            amount: The order amount (positive for buy, negative for sell).
            portfolio: The algorithm's portfolio state.
            algo_datetime: The current algorithm datetime.
            algo_current_data: The current bar data.

        Returns:
            None: If order passes validation.

        Raises:
            TradingControlViolation: If on_error="fail" and constraint is violated.

        Note:
            Implementations must call handle_violation() when constraints are violated.
        """
        raise NotImplementedError

    def _constraint_msg(self, metadata):
        """Build constraint message with optional metadata.

        Args:
            metadata: Optional dictionary of additional constraint information.

        Returns:
            str: The constraint message including metadata if provided.
        """
        constraint = repr(self)
        if metadata:
            constraint = f"{constraint} (Metadata: {metadata})"
        return constraint

    def handle_violation(self, asset, amount, datetime, metadata=None):
        """Handle a trading control violation.

        Based on the on_error setting, either raises an exception or logs a
        warning when a trading constraint is violated.

        Args:
            asset: The asset that triggered the violation.
            amount: The order amount that triggered the violation.
            datetime: The datetime of the violation.
            metadata: Optional dictionary of additional violation details.

        Raises:
            TradingControlViolation: If on_error="fail".

        Examples:
            >>> # This is called internally when a constraint is violated
            >>> control.handle_violation(
            ...     asset=stock,
            ...     amount=1000,
            ...     datetime=algo_datetime,
            ...     metadata={"limit": 500}
            ... )
        """
        constraint = self._constraint_msg(metadata)

        if self.on_error == "fail":
            raise TradingControlViolation(
                asset=asset, amount=amount, datetime=datetime, constraint=constraint
            )
        elif self.on_error == "log":
            log.error(
                "Order for %(amount)s shares of %(asset)s at %(dt)s "
                "violates trading constraint %(constraint)s",
                dict(amount=amount, asset=asset, dt=datetime, constraint=constraint),
            )

    def __repr__(self):
        """Return string representation of the control.

        Returns:
            str: Control class name with fail_args parameters.
        """
        return f"{self.__class__.__name__}({self.__fail_args})"


class MaxOrderCount(TradingControl):
    """Limit the number of orders that can be placed in a single trading day.

    This control prevents algorithms from placing an excessive number of orders
    per day, which can help avoid:
    - Excessive trading costs
    - Potential algorithm bugs causing runaway trading
    - Broker order rate limits

    The counter resets automatically at the start of each new trading day.

    Args:
        on_error: How to handle violations ("fail" or "log").
        max_count: Maximum number of orders allowed per day.

    Attributes:
        orders_placed: Number of orders placed today (resets daily).
        max_count: The maximum allowed orders per day.
        current_date: The current trading date (for reset tracking).

    Examples:
        >>> from rustybt.finance.controls import MaxOrderCount
        >>> # Limit to 100 orders per day
        >>> control = MaxOrderCount(on_error="fail", max_count=100)
        >>>
        >>> # Typically used via the API:
        >>> from rustybt.api import set_max_order_count
        >>> set_max_order_count(100)

    Raises:
        TradingControlViolation: If on_error="fail" and limit is exceeded.
    """

    def __init__(self, on_error, max_count):
        """Initialize max order count control.

        Args:
            on_error: Violation handling mode ("fail" or "log").
            max_count: Maximum orders allowed per trading day.
        """
        super(MaxOrderCount, self).__init__(on_error, max_count=max_count)
        self.orders_placed = 0
        self.max_count = max_count
        self.current_date = None

    def validate(self, asset, amount, portfolio, algo_datetime, algo_current_data):
        """Validate that daily order limit hasn't been exceeded.

        Increments the daily order counter and checks if it exceeds max_count.
        Automatically resets the counter at the start of a new trading day.

        Args:
            asset: The asset being ordered (unused).
            amount: The order amount (unused).
            portfolio: The portfolio state (unused).
            algo_datetime: The current algorithm datetime.
            algo_current_data: The current bar data (unused).

        Raises:
            TradingControlViolation: If order would exceed daily limit.
        """
        algo_date = algo_datetime.date()

        # Reset order count if it's a new day.
        if self.current_date and self.current_date != algo_date:
            self.orders_placed = 0
        self.current_date = algo_date

        if self.orders_placed >= self.max_count:
            self.handle_violation(asset, amount, algo_datetime)
        self.orders_placed += 1


class RestrictedListOrder(TradingControl):
    """Prevent trading in restricted assets.

    This control maintains a list of assets that cannot be traded, which is
    useful for compliance requirements such as:
    - Insider trading blackout periods
    - Regulatory restrictions
    - Internal compliance policies

    The restriction list can be time-dependent, allowing restrictions to
    apply only during specific date ranges.

    Args:
        on_error: How to handle violations ("fail" or "log").
        restrictions: Restrictions object defining which assets are restricted.

    Attributes:
        restrictions: The asset restrictions configuration.

    Examples:
        >>> from rustybt.finance.asset_restrictions import Restrictions
        >>> from rustybt.finance.controls import RestrictedListOrder
        >>>
        >>> # Create restrictions for specific assets
        >>> restrictions = Restrictions(restricted_list=[stock1, stock2])
        >>> control = RestrictedListOrder(on_error="fail", restrictions=restrictions)

    Raises:
        TradingControlViolation: If attempting to trade a restricted asset.
    """

    def __init__(self, on_error, restrictions):
        """Initialize restricted list control.

        Args:
            on_error: Violation handling mode ("fail" or "log").
            restrictions: Restrictions object defining restricted assets.
        """
        super(RestrictedListOrder, self).__init__(on_error)
        self.restrictions = restrictions

    def validate(self, asset, amount, portfolio, algo_datetime, algo_current_data):
        """Validate that the asset is not on the restricted list.

        Checks if the asset is restricted at the current datetime. Restrictions
        can be time-dependent, so an asset may only be restricted during
        certain date ranges.

        Args:
            asset: The asset being ordered.
            amount: The order amount (unused).
            portfolio: The portfolio state (unused).
            algo_datetime: The current algorithm datetime.
            algo_current_data: The current bar data (unused).

        Raises:
            TradingControlViolation: If asset is currently restricted.
        """
        if self.restrictions.is_restricted(asset, algo_datetime):
            self.handle_violation(asset, amount, algo_datetime)


class MaxOrderSize(TradingControl):
    """Limit the size of individual orders by shares or dollar value.

    This control prevents placing orders that exceed specified size limits,
    which helps:
    - Prevent oversized orders due to algorithm bugs
    - Enforce risk management policies
    - Respect broker order size limits
    - Control market impact

    Limits can be specified for a specific asset or applied globally to all assets.

    Args:
        on_error: How to handle violations ("fail" or "log").
        asset: Specific asset to apply limit to (None for all assets).
        max_shares: Maximum order size in shares (optional).
        max_notional: Maximum order size in dollar value (optional).

    Attributes:
        asset: The asset this control applies to (None for all assets).
        max_shares: Maximum shares per order.
        max_notional: Maximum dollar value per order.

    Examples:
        >>> from rustybt.finance.controls import MaxOrderSize
        >>> # Limit all orders to 10,000 shares
        >>> control = MaxOrderSize(on_error="fail", max_shares=10000)
        >>>
        >>> # Limit orders to $100,000 notional value
        >>> control = MaxOrderSize(on_error="fail", max_notional=100000)
        >>>
        >>> # Limit specific asset to 1,000 shares AND $50,000
        >>> control = MaxOrderSize(
        ...     on_error="fail",
        ...     asset=stock,
        ...     max_shares=1000,
        ...     max_notional=50000
        ... )

    Raises:
        ValueError: If neither max_shares nor max_notional is provided.
        ValueError: If max_shares or max_notional is negative.
        TradingControlViolation: If order exceeds size limits.
    """

    def __init__(self, on_error, asset=None, max_shares=None, max_notional=None):
        """Initialize max order size control.

        Args:
            on_error: Violation handling mode ("fail" or "log").
            asset: Asset to apply limit to (None for all assets).
            max_shares: Maximum shares per order (optional).
            max_notional: Maximum dollar value per order (optional).

        Raises:
            ValueError: If neither limit is specified or if limits are negative.
        """
        super(MaxOrderSize, self).__init__(
            on_error, asset=asset, max_shares=max_shares, max_notional=max_notional
        )
        self.asset = asset
        self.max_shares = max_shares
        self.max_notional = max_notional

        if max_shares is None and max_notional is None:
            raise ValueError("Must supply at least one of max_shares and max_notional")

        if max_shares and max_shares < 0:
            raise ValueError("max_shares cannot be negative.")

        if max_notional and max_notional < 0:
            raise ValueError("max_notional must be positive.")

    def validate(self, asset, amount, portfolio, algo_datetime, algo_current_data):
        """Validate that order size doesn't exceed limits.

        Checks both share count and notional value limits (if specified).
        If this control is asset-specific, only validates orders for that asset.

        Args:
            asset: The asset being ordered.
            amount: The order amount (positive for buy, negative for sell).
            portfolio: The portfolio state (unused).
            algo_datetime: The current algorithm datetime (unused).
            algo_current_data: The current bar data (for price lookup).

        Raises:
            TradingControlViolation: If order size exceeds limits.
        """
        if self.asset is not None and self.asset != asset:
            return

        if self.max_shares is not None and abs(amount) > self.max_shares:
            self.handle_violation(asset, amount, algo_datetime)

        current_asset_price = algo_current_data.current(asset, "price")
        order_value = amount * current_asset_price

        too_much_value = self.max_notional is not None and abs(order_value) > self.max_notional

        if too_much_value:
            self.handle_violation(asset, amount, algo_datetime)


class MaxPositionSize(TradingControl):
    """TradingControl representing a limit on the maximum position size that can
    be held by an algo for a given asset.
    """

    def __init__(self, on_error, asset=None, max_shares=None, max_notional=None):
        super(MaxPositionSize, self).__init__(
            on_error, asset=asset, max_shares=max_shares, max_notional=max_notional
        )
        self.asset = asset
        self.max_shares = max_shares
        self.max_notional = max_notional

        if max_shares is None and max_notional is None:
            raise ValueError("Must supply at least one of max_shares and max_notional")

        if max_shares and max_shares < 0:
            raise ValueError("max_shares cannot be negative.")

        if max_notional and max_notional < 0:
            raise ValueError("max_notional must be positive.")

    def validate(self, asset, amount, portfolio, algo_datetime, algo_current_data):
        """Fail if the given order would cause the magnitude of our position to be
        greater in shares than self.max_shares or greater in dollar value than
        self.max_notional.
        """
        if self.asset is not None and self.asset != asset:
            return

        current_share_count = portfolio.positions[asset].amount
        shares_post_order = current_share_count + amount

        too_many_shares = self.max_shares is not None and abs(shares_post_order) > self.max_shares
        if too_many_shares:
            self.handle_violation(asset, amount, algo_datetime)

        current_price = algo_current_data.current(asset, "price")
        value_post_order = shares_post_order * current_price

        too_much_value = self.max_notional is not None and abs(value_post_order) > self.max_notional

        if too_much_value:
            self.handle_violation(asset, amount, algo_datetime)


class LongOnly(TradingControl):
    """Prevent short positions (long-only trading constraint).

    This control ensures that the algorithm can only hold long positions,
    preventing any trades that would result in negative (short) share positions.
    This is useful for:
    - Strategies that are long-only by design
    - Accounts that don't allow short selling
    - Regulatory or policy restrictions

    Args:
        on_error: How to handle violations ("fail" or "log").

    Examples:
        >>> from rustybt.finance.controls import LongOnly
        >>> control = LongOnly(on_error="fail")
        >>>
        >>> # Typically used via the API:
        >>> from rustybt.api import set_long_only
        >>> set_long_only()

    Raises:
        TradingControlViolation: If order would create a short position.
    """

    def __init__(self, on_error):
        """Initialize long-only control.

        Args:
            on_error: Violation handling mode ("fail" or "log").
        """
        super(LongOnly, self).__init__(on_error)

    def validate(self, asset, amount, portfolio, algo_datetime, algo_current_data):
        """Validate that order won't create a short position.

        Checks if completing this order would result in a negative share
        position for the asset, which would constitute a short position.

        Args:
            asset: The asset being ordered.
            amount: The order amount (positive for buy, negative for sell).
            portfolio: The portfolio state (contains current positions).
            algo_datetime: The current algorithm datetime (unused).
            algo_current_data: The current bar data (unused).

        Raises:
            TradingControlViolation: If order would result in negative shares.

        Examples:
            >>> # If currently holding 100 shares, selling 150 would violate
            >>> # because final position would be -50 shares
            >>> control.validate(asset, -150, portfolio, datetime, data)
            TradingControlViolation: ...
        """
        if portfolio.positions[asset].amount + amount < 0:
            self.handle_violation(asset, amount, algo_datetime)


class AssetDateBounds(TradingControl):
    """TradingControl representing a prohibition against ordering an asset before
    its start_date, or after its end_date.
    """

    def __init__(self, on_error):
        super(AssetDateBounds, self).__init__(on_error)

    def validate(self, asset, amount, portfolio, algo_datetime, algo_current_data):
        """Fail if the algo has passed this Asset's end_date, or before the
        Asset's start date.
        """
        # If the order is for 0 shares, then silently pass through.
        if amount == 0:
            return

        normalized_algo_dt = algo_datetime.normalize().tz_localize(None)

        # Fail if the algo is before this Asset's start_date
        if asset.start_date:
            normalized_start = asset.start_date.normalize()
            if normalized_algo_dt < normalized_start:
                metadata = {"asset_start_date": normalized_start}
                self.handle_violation(asset, amount, algo_datetime, metadata=metadata)
        # Fail if the algo has passed this Asset's end_date
        if asset.end_date:
            normalized_end = asset.end_date.normalize()
            if normalized_algo_dt > normalized_end:
                metadata = {"asset_end_date": normalized_end}
                self.handle_violation(asset, amount, algo_datetime, metadata=metadata)


class AccountControl(metaclass=abc.ABCMeta):
    """Abstract base class for account-level fail-safe controls.

    Account controls monitor the overall state of an algorithm's account
    (leverage, equity, etc.) and enforce constraints on a per-bar basis
    rather than per-order. They are validated during each call to handle_data.

    Unlike TradingControl (which validates individual orders), AccountControl
    monitors aggregate account metrics and can halt execution if thresholds
    are exceeded.

    Attributes:
        _AccountControl__fail_args: Arguments to include in error messages.

    Examples:
        >>> from rustybt.finance.controls import MaxLeverage
        >>> control = MaxLeverage(max_leverage=2.0)
        >>> # During backtesting, control.validate() is called each bar
    """

    def __init__(self, **kwargs):
        """Initialize account control.

        Args:
            **kwargs: Additional arguments to display in error messages.
        """
        self.__fail_args = kwargs

    @abc.abstractmethod
    def validate(self, _portfolio, _account, _algo_datetime, _algo_current_data):
        """Validate that account state doesn't violate this control's constraint.

        This method is called exactly once per registered AccountControl on
        each call to handle_data. If the account passes validation, it should
        return None with no side effects. If the account violates the
        constraint, it should call fail().

        Args:
            _portfolio: The algorithm's portfolio state.
            _account: The algorithm's account state.
            _algo_datetime: The current algorithm datetime.
            _algo_current_data: The current bar data.

        Returns:
            None: If account passes validation.

        Raises:
            AccountControlViolation: If constraint is violated.

        Note:
            Implementations must call fail() when constraints are violated.
        """
        raise NotImplementedError

    def fail(self):
        """Raise an AccountControlViolation exception.

        This method is called by validate() implementations when a constraint
        is violated. It always raises an exception to halt algorithm execution.

        Raises:
            AccountControlViolation: Always raised with constraint information.
        """
        raise AccountControlViolation(constraint=repr(self))

    def __repr__(self):
        """Return string representation of the control.

        Returns:
            str: Control class name with fail_args parameters.
        """
        return f"{self.__class__.__name__}({self.__fail_args})"


class MaxLeverage(AccountControl):
    """Limit the maximum leverage allowed for the algorithm.

    This control monitors gross leverage (total exposure / equity) and halts
    execution if the algorithm exceeds the specified maximum leverage. This
    is critical for:
    - Risk management and position sizing
    - Regulatory compliance
    - Margin call prevention
    - Drawdown control

    Leverage is calculated as: (long_value + short_value) / portfolio_value

    Args:
        max_leverage: Maximum allowed gross leverage (e.g., 2.0 for 2x leverage).

    Attributes:
        max_leverage: The maximum leverage threshold.

    Examples:
        >>> from rustybt.finance.controls import MaxLeverage
        >>> # Limit leverage to 2x (200% gross exposure)
        >>> control = MaxLeverage(max_leverage=2.0)
        >>>
        >>> # Typically used via the API:
        >>> from rustybt.api import set_max_leverage
        >>> set_max_leverage(2.0)

    Raises:
        ValueError: If max_leverage is None or negative.
        AccountControlViolation: If account leverage exceeds limit.
    """

    def __init__(self, max_leverage):
        """Initialize max leverage control.

        Args:
            max_leverage: Maximum gross leverage in decimal form. For example,
                2.0 limits an algorithm to trading at most double the account value
                (200% gross exposure).

        Raises:
            ValueError: If max_leverage is None or negative.
        """
        super(MaxLeverage, self).__init__(max_leverage=max_leverage)
        self.max_leverage = max_leverage

        if max_leverage is None:
            raise ValueError("Must supply max_leverage")

        if max_leverage < 0:
            raise ValueError("max_leverage must be positive")

    def validate(self, _portfolio, _account, _algo_datetime, _algo_current_data):
        """Validate that current leverage doesn't exceed maximum.

        Checks the account's current gross leverage against the configured
        maximum. If exceeded, halts algorithm execution.

        Args:
            _portfolio: The portfolio state (unused).
            _account: The account state (contains leverage).
            _algo_datetime: The current datetime (unused).
            _algo_current_data: The current bar data (unused).

        Raises:
            AccountControlViolation: If current leverage exceeds max_leverage.

        Examples:
            >>> # If max_leverage=2.0 and current leverage is 2.5, this raises
            >>> control.validate(portfolio, account, datetime, data)
            AccountControlViolation: ...
        """
        if _account.leverage > self.max_leverage:
            self.fail()


class MinLeverage(AccountControl):
    """Enforce minimum leverage after a specified deadline.

    This control ensures that the algorithm maintains at least a minimum
    level of leverage after a specified deadline. This is useful for:
    - Ensuring capital deployment in production strategies
    - Meeting fund mandate requirements
    - Preventing algorithm from becoming too conservative over time

    The control only activates after the deadline has passed. Before the
    deadline, no minimum leverage is enforced.

    Args:
        min_leverage: Minimum required gross leverage (e.g., 2.0 for 2x).
        deadline: The datetime after which minimum leverage is enforced.

    Attributes:
        min_leverage: The minimum leverage threshold.
        deadline: The activation datetime for this control.

    Examples:
        >>> from datetime import datetime
        >>> from rustybt.finance.controls import MinLeverage
        >>>
        >>> # Require 2x leverage after January 1, 2024
        >>> control = MinLeverage(
        ...     min_leverage=2.0,
        ...     deadline=datetime(2024, 1, 1)
        ... )
        >>>
        >>> # Before deadline: no enforcement
        >>> # After deadline: algorithm must maintain >= 2x leverage

    Raises:
        AccountControlViolation: If leverage is below minimum after deadline.

    Note:
        For example, min_leverage=2.0 requires the algorithm to trade at
        minimum double the account value (200% gross exposure) by the deadline.
    """

    @expect_types(__funcname="MinLeverage", min_leverage=(int, float), deadline=datetime)
    @expect_bounded(__funcname="MinLeverage", min_leverage=(0, None))
    def __init__(self, min_leverage, deadline):
        """Initialize min leverage control.

        Args:
            min_leverage: Minimum gross leverage required after deadline.
            deadline: The datetime when minimum leverage enforcement begins.

        Note:
            Input validation is performed by decorators:
            - expect_types ensures correct parameter types
            - expect_bounded ensures min_leverage >= 0
        """
        super(MinLeverage, self).__init__(min_leverage=min_leverage, deadline=deadline)
        self.min_leverage = min_leverage
        self.deadline = deadline

    def validate(self, _portfolio, account, algo_datetime, _algo_current_data):
        """Validate minimum leverage if past deadline.

        Only performs validation if the current algorithm datetime is after
        the configured deadline. Before the deadline, this control has no effect.

        Args:
            _portfolio: The portfolio state (unused).
            account: The account state (contains leverage).
            algo_datetime: The current algorithm datetime.
            _algo_current_data: The current bar data (unused).

        Raises:
            AccountControlViolation: If past deadline and leverage is below minimum.

        Examples:
            >>> # Before deadline: passes regardless of leverage
            >>> control.validate(portfolio, account, datetime(2023, 12, 31), data)
            >>> # OK - before deadline
            >>>
            >>> # After deadline with low leverage: fails
            >>> control.validate(portfolio, low_leverage_account, datetime(2024, 1, 2), data)
            AccountControlViolation: ...
        """
        if (
            algo_datetime > self.deadline.tz_localize(algo_datetime.tzinfo)
            and account.leverage < self.min_leverage
        ):
            self.fail()
