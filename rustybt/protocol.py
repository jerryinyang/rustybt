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
"""Protocol definitions for algorithm state and market data access.

This module defines the core data structures used by trading algorithms to
access portfolio state, account information, and market data during backtests.
These classes provide read-only interfaces to prevent accidental state mutations
in user algorithm code.

Key Classes:
    Portfolio: Read-only portfolio state including positions, cash, and values
    Account: Account-level information including margin and leverage
    Position: Individual asset position with cost basis and current value
    Positions: Dict-like container for all positions with automatic defaults
    Event: Generic event data structure for algorithm events
    BarData: Market data access interface (imported from _protocol)

Data Source Types:
    DATASOURCE_TYPE: Enumeration of event types in the simulation:
        - AS_TRADED_EQUITY: Real-time equity data
        - SPLIT, MERGER, DIVIDEND: Corporate actions
        - TRADE, TRANSACTION, ORDER: Trading events
        - BENCHMARK, COMMISSION: Performance tracking
        - CUSTOM: User-defined events

Design Pattern:
    These classes use immutability patterns to protect algorithm state:
    - Portfolio, Account, Position: Raise AttributeError on mutation attempts
    - MutableView: Internal helper for controlled state updates
    - Read-only properties provide safe data access

Examples:
    Accessing portfolio information:
        >>> def handle_data(context, data):
        ...     portfolio = context.portfolio
        ...     print(f"Cash: ${portfolio.cash:.2f}")
        ...     print(f"Portfolio value: ${portfolio.portfolio_value:.2f}")
        ...     print(f"Positions: {len(portfolio.positions)}")

    Accessing position details:
        >>> def handle_data(context, data):
        ...     pos = context.portfolio.positions[symbol('AAPL')]
        ...     print(f"Shares: {pos.amount}")
        ...     print(f"Cost basis: ${pos.cost_basis:.2f}")
        ...     print(f"Last price: ${pos.last_sale_price:.2f}")

    Computing portfolio weights:
        >>> weights = context.portfolio.current_portfolio_weights
        >>> for asset, weight in weights.items():
        ...     print(f"{asset.symbol}: {weight:.2%}")
"""
from enum import IntEnum

import pandas as pd

from ._protocol import BarData, InnerPosition
from .assets import Asset


class MutableView:
    """A mutable view over an "immutable" object.

    This helper class provides controlled mutability for objects that should
    appear immutable to external code. It's used internally during object
    initialization to set up state, while the object itself blocks direct
    attribute assignment.

    The view delegates attribute access to the wrapped object but allows
    modification of the underlying object's __dict__. This pattern is used
    by Portfolio and Account to enable internal state updates while preventing
    user code from accidentally modifying algorithm state.

    Args:
        ob: The object to wrap with a mutable view.

    Examples:
        >>> class ImmutableClass:
        ...     def __init__(self):
        ...         view = MutableView(self)
        ...         view.value = 42  # Works via view
        ...     def __setattr__(self, attr, value):
        ...         raise AttributeError("Immutable!")
        ...
        >>> obj = ImmutableClass()
        >>> obj.value  # Reading works
        42
        >>> obj.value = 100  # Direct setting blocked
        AttributeError: Immutable!

    Note:
        This is an internal implementation detail. User code should not
        create MutableView instances directly.
    """

    # add slots so we don't accidentally add attributes to the view instead of
    # ``ob``
    __slots__ = ("_mutable_view_ob",)

    def __init__(self, ob):
        """Initialize view over target object.

        Args:
            ob: The object to provide a mutable view over.
        """
        object.__setattr__(self, "_mutable_view_ob", ob)

    def __getattr__(self, attr):
        """Get attribute from the wrapped object.

        Args:
            attr (str): Name of attribute to retrieve.

        Returns:
            The value of the attribute from the wrapped object.
        """
        return getattr(self._mutable_view_ob, attr)

    def __setattr__(self, attr, value):
        """Set attribute on the wrapped object's __dict__.

        Args:
            attr (str): Name of attribute to set.
            value: Value to assign to the attribute.
        """
        vars(self._mutable_view_ob)[attr] = value

    def __repr__(self):
        return f"{type(self).__name__}({self._mutable_view_ob!r})"


# Datasource type should completely determine the other fields of a
# message with its type.
DATASOURCE_TYPE = IntEnum(
    "DATASOURCE_TYPE",
    [
        "AS_TRADED_EQUITY",
        "MERGER",
        "SPLIT",
        "DIVIDEND",
        "TRADE",
        "TRANSACTION",
        "ORDER",
        "EMPTY",
        "DONE",
        "CUSTOM",
        "BENCHMARK",
        "COMMISSION",
        "CLOSE_POSITION",
    ],
    start=0,
)

# Expected fields/index values for a dividend Series.
DIVIDEND_FIELDS = [
    "declared_date",
    "ex_date",
    "gross_amount",
    "net_amount",
    "pay_date",
    "payment_sid",
    "ratio",
    "sid",
]
# Expected fields/index values for a dividend payment Series.
DIVIDEND_PAYMENT_FIELDS = [
    "id",
    "payment_sid",
    "cash_amount",
    "share_count",
]


class Event:
    """Generic event data container for algorithm events.

    A flexible container for event data that stores arbitrary key-value pairs
    as attributes. Events can be created with initial values and converted to
    pandas Series for analysis.

    Args:
        initial_values (dict, optional): Dictionary of initial attribute values
            to set on the event. Keys become attributes, values become their values.

    Attributes:
        Dynamic attributes based on initial_values or subsequent assignments.

    Examples:
        Creating events:
            >>> event = Event({'price': 100.50, 'volume': 1000})
            >>> event.price
            100.50
            >>> event.volume
            1000

        Converting to Series:
            >>> event = Event({'open': 100, 'high': 105, 'low': 99, 'close': 103})
            >>> series = event.to_series()
            >>> series['close']
            103

        Checking for attributes:
            >>> 'price' in event
            True
            >>> 'nonexistent' in event
            False
    """

    def __init__(self, initial_values=None):
        """Initialize event with optional initial values.

        Args:
            initial_values (dict, optional): Initial key-value pairs to set
                as attributes on this event.
        """
        if initial_values:
            self.__dict__.update(initial_values)

    def keys(self):
        """Get all attribute names.

        Returns:
            dict_keys: The keys of the event's attribute dictionary.
        """
        return self.__dict__.keys()

    def __eq__(self, other):
        """Check equality based on attribute dictionaries.

        Args:
            other: Another object to compare with.

        Returns:
            bool: True if other has same attributes and values, False otherwise.
        """
        return hasattr(other, "__dict__") and self.__dict__ == other.__dict__

    def __contains__(self, name):
        """Check if attribute exists on this event.

        Args:
            name (str): Attribute name to check.

        Returns:
            bool: True if attribute exists, False otherwise.
        """
        return name in self.__dict__

    def __repr__(self):
        return f"Event({self.__dict__})"

    def to_series(self, index=None):
        """Convert event to pandas Series.

        Args:
            index (list, optional): Explicit index to use for the Series.
                If None, uses the event's attribute names.

        Returns:
            pd.Series: Series representation of the event's attributes.
        """
        return pd.Series(self.__dict__, index=index)


class Order(Event):
    """Order event containing order details.

    Specialized Event subclass for order-related information. Inherits all
    Event functionality for flexible attribute storage.

    See Also:
        Event: Base event class
    """

    pass


class Portfolio:
    """Object providing read-only access to current portfolio state.

    Parameters
    ----------
    start_date : pd.Timestamp
        The start date for the period being recorded.
    capital_base : float
        The starting value for the portfolio. This will be used as the starting
        cash, current cash, and portfolio value.

    Attributes:
    ----------
    positions : zipline.protocol.Positions
        Dict-like object containing information about currently-held positions.
    cash : float
        Amount of cash currently held in portfolio.
    portfolio_value : float
        Current liquidation value of the portfolio's holdings.
        This is equal to ``cash + sum(shares * price)``
    starting_cash : float
        Amount of cash in the portfolio at the start of the backtest.
    """

    def __init__(self, start_date=None, capital_base=0.0):
        self_ = MutableView(self)
        self_.cash_flow = 0.0
        self_.starting_cash = capital_base
        self_.portfolio_value = capital_base
        self_.pnl = 0.0
        self_.returns = 0.0
        self_.cash = capital_base
        self_.positions = Positions()
        self_.start_date = start_date
        self_.positions_value = 0.0
        self_.positions_exposure = 0.0

    @property
    def capital_used(self):
        return self.cash_flow

    def __setattr__(self, attr, value):
        raise AttributeError("cannot mutate Portfolio objects")

    def __repr__(self):
        return f"Portfolio({self.__dict__})"

    @property
    def current_portfolio_weights(self):
        """Compute each asset's weight in the portfolio.

        Calculates the percentage of total portfolio value represented by each
        position. Position values are computed differently for different asset types:

        - Equities: price * shares
        - Futures: price * shares * contract_multiplier

        Returns:
            pd.Series: Portfolio weights indexed by asset, with values between
                -1 and 1 (negative for short positions). Weights sum to
                positions_value / portfolio_value.

        Examples:
            >>> weights = context.portfolio.current_portfolio_weights
            >>> weights[symbol('AAPL')]
            0.15  # AAPL represents 15% of portfolio
            >>> weights[symbol('TSLA')]
            -0.05  # Short position, 5% of portfolio

            Rebalancing to target weights:
                >>> target_weights = {'AAPL': 0.30, 'GOOGL': 0.40, 'MSFT': 0.30}
                >>> current_weights = context.portfolio.current_portfolio_weights
                >>> for symbol_str, target_weight in target_weights.items():
                ...     asset = symbol(symbol_str)
                ...     current_weight = current_weights.get(asset, 0)
                ...     weight_diff = target_weight - current_weight
                ...     target_value = weight_diff * context.portfolio.portfolio_value
                ...     order_target_value(asset, target_value)

        Note:
            - Cash is not included in the weights (only positions)
            - Short positions have negative weights
            - Sum of weights typically less than 1 due to cash holdings
        """
        position_values = pd.Series(
            {
                asset: (position.last_sale_price * position.amount * asset.price_multiplier)
                for asset, position in self.positions.items()
            },
            dtype=float,
        )
        return position_values / self.portfolio_value


class Account:
    """Read-only account information for margin and broker-reported values.

    The Account object tracks detailed account-level information including
    margin requirements, buying power, and leverage. These values are updated
    throughout the backtest and can be synchronized with live broker values
    in live trading mode.

    Attributes:
        settled_cash (float): Cash available for trading (settled funds).
        accrued_interest (float): Interest accrued on account.
        buying_power (float): Maximum purchasing power available. Default: inf
        equity_with_loan (float): Account equity including borrowed funds.
        total_positions_value (float): Total market value of all positions.
        total_positions_exposure (float): Total exposure across positions.
        regt_equity (float): Regulation T equity.
        regt_margin (float): Regulation T margin. Default: inf
        initial_margin_requirement (float): Initial margin required for positions.
        maintenance_margin_requirement (float): Maintenance margin required.
        available_funds (float): Funds available for new positions.
        excess_liquidity (float): Liquidity above margin requirements.
        cushion (float): Margin cushion (excess / net_liquidation).
        day_trades_remaining (float): Day trades available. Default: inf
        leverage (float): Portfolio leverage (positions / equity).
        net_leverage (float): Net portfolio leverage (long - short) / equity.
        net_liquidation (float): Net liquidation value of account.

    Examples:
        Checking margin usage:
            >>> def handle_data(context, data):
            ...     account = context.account
            ...     print(f"Leverage: {account.leverage:.2f}")
            ...     print(f"Buying power: ${account.buying_power:,.2f}")
            ...     if account.leverage > 1.5:
            ...         print("WARNING: High leverage!")

        Monitoring margin requirements:
            >>> def handle_data(context, data):
            ...     margin_used = context.account.initial_margin_requirement
            ...     margin_avail = context.account.available_funds
            ...     margin_pct = margin_used / (margin_used + margin_avail)
            ...     print(f"Margin utilization: {margin_pct:.1%}")

    Note:
        - Account objects are immutable; attempting to set attributes raises AttributeError
        - In backtesting, some values default to infinity (e.g., buying_power)
        - In live trading, values are synchronized from broker
    """

    def __init__(self):
        """Initialize account with default values.

        All margin-related fields are set to appropriate defaults for backtesting.
        """
        self_ = MutableView(self)
        self_.settled_cash = 0.0
        self_.accrued_interest = 0.0
        self_.buying_power = float("inf")
        self_.equity_with_loan = 0.0
        self_.total_positions_value = 0.0
        self_.total_positions_exposure = 0.0
        self_.regt_equity = 0.0
        self_.regt_margin = float("inf")
        self_.initial_margin_requirement = 0.0
        self_.maintenance_margin_requirement = 0.0
        self_.available_funds = 0.0
        self_.excess_liquidity = 0.0
        self_.cushion = 0.0
        self_.day_trades_remaining = float("inf")
        self_.leverage = 0.0
        self_.net_leverage = 0.0
        self_.net_liquidation = 0.0

    def __setattr__(self, attr, value):
        """Prevent mutation of Account attributes.

        Raises:
            AttributeError: Always raised to prevent account mutation.
        """
        raise AttributeError("cannot mutate Account objects")

    def __repr__(self):
        return f"Account({self.__dict__})"


class Position:
    """An individual asset position held by the algorithm.

    Represents a position (long or short) in a specific asset, including
    cost basis, current price, and quantity held. Position objects are
    immutable to prevent accidental modifications to algorithm state.

    Attributes:
        asset (Asset): The asset being held in this position.
        amount (int): Number of shares held. Negative values represent
            short positions, positive values represent long positions.
        cost_basis (float): Average price paid per share for currently-held
            shares. For short positions, this is the average price received.
        last_sale_price (float): Most recent market price for the asset.
        last_sale_date (pd.Timestamp): Timestamp when last_sale_price was
            last updated.
        sid (Asset): Alias for `asset` (backwards compatibility).

    Examples:
        Accessing position information:
            >>> pos = context.portfolio.positions[symbol('AAPL')]
            >>> print(f"Shares: {pos.amount}")
            100
            >>> print(f"Cost basis: ${pos.cost_basis:.2f}")
            150.25
            >>> print(f"Current price: ${pos.last_sale_price:.2f}")
            155.50
            >>> print(f"P&L: ${(pos.last_sale_price - pos.cost_basis) * pos.amount:.2f}")
            525.00

        Checking for short positions:
            >>> for asset, pos in context.portfolio.positions.items():
            ...     if pos.amount < 0:
            ...         print(f"Short position: {asset.symbol}, {abs(pos.amount)} shares")

        Computing position value:
            >>> pos = context.portfolio.positions[symbol('TSLA')]
            >>> position_value = pos.amount * pos.last_sale_price
            >>> print(f"Position value: ${position_value:,.2f}")

    Note:
        - Position objects are immutable; attempts to modify raise AttributeError
        - Empty positions (amount=0) may still appear in positions dict
        - Position value doesn't account for asset.price_multiplier (use Portfolio methods)
    """

    __slots__ = ("_underlying_position",)

    def __init__(self, underlying_position):
        """Initialize position wrapper.

        Args:
            underlying_position (InnerPosition): The internal position object.
        """
        object.__setattr__(self, "_underlying_position", underlying_position)

    def __getattr__(self, attr):
        """Delegate attribute access to underlying position.

        Args:
            attr (str): Attribute name to retrieve.

        Returns:
            The value of the attribute from the underlying position.
        """
        return getattr(self._underlying_position, attr)

    def __setattr__(self, attr, value):
        """Prevent mutation of Position attributes.

        Raises:
            AttributeError: Always raised to prevent position mutation.
        """
        raise AttributeError("cannot mutate Position objects")

    @property
    def sid(self):
        """Get the position's asset (backwards compatibility alias).

        Returns:
            Asset: The asset for this position (same as .asset).
        """
        # for backwards compatibility
        return self.asset

    def __repr__(self):
        return "Position(%r)" % {
            k: getattr(self, k)
            for k in (
                "asset",
                "amount",
                "cost_basis",
                "last_sale_price",
                "last_sale_date",
            )
        }


class Positions(dict):
    """Dict-like container for all algorithm positions with automatic defaults.

    A specialized dictionary that maps Assets to Position objects. Automatically
    returns an empty Position for assets not currently held, eliminating the
    need for defensive key checking.

    This allows safe access patterns like:
        >>> pos = context.portfolio.positions[some_asset]  # Never raises KeyError

    Examples:
        Iterating over positions:
            >>> for asset, position in context.portfolio.positions.items():
            ...     print(f"{asset.symbol}: {position.amount} shares")

        Accessing non-existent positions:
            >>> never_owned = symbol('NEVER_OWNED')
            >>> pos = context.portfolio.positions[never_owned]
            >>> pos.amount  # Returns 0, not an error
            0

        Checking if position exists:
            >>> asset = symbol('AAPL')
            >>> if asset in context.portfolio.positions:
            ...     pos = context.portfolio.positions[asset]
            ...     if pos.amount != 0:
            ...         print(f"Holding {pos.amount} shares")

        Safe position lookups:
            >>> # No need for .get() or try/except
            >>> shares_held = context.portfolio.positions[asset].amount

    Note:
        - Missing keys return empty Position objects (amount=0)
        - Only Asset objects are valid keys
        - Inherited dict methods (keys(), values(), items()) work normally
    """

    def __missing__(self, key):
        """Return empty position for assets not currently held.

        Args:
            key (Asset): The asset to look up.

        Returns:
            Position: An empty position (amount=0) for the asset.

        Raises:
            ValueError: If key is not an Asset instance.
        """
        if isinstance(key, Asset):
            return Position(InnerPosition(key))

        raise ValueError(
            f"Position lookup expected a value of type Asset but got {type(key).__name__} instead"
        )
