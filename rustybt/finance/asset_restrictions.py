"""Asset trading restrictions for compliance and risk management.

This module provides classes for managing restricted asset lists, which prevent
algorithms from trading certain assets. Restrictions can be:
- Static: Fixed list of forbidden assets
- Historical: Time-dependent restrictions with effective dates
- Security-list based: Dynamic restrictions from security lists

Restrictions are commonly used for:
- Compliance: Preventing trades in restricted securities
- Risk management: Blacklisting problematic assets
- Testing: Simulating real-world trading constraints

Example:
    Creating static restrictions::

        from rustybt.finance.asset_restrictions import StaticRestrictions

        # Prevent trading in specific stocks
        blacklist = [stock_a, stock_b, stock_c]
        restrictions = StaticRestrictions(blacklist)

        # Check if asset is restricted
        if restrictions.is_restricted(my_asset, current_dt):
            # Skip this asset
            pass

    Creating time-dependent restrictions::

        from rustybt.finance.asset_restrictions import (
            HistoricalRestrictions,
            Restriction,
            RESTRICTION_STATES
        )

        restrictions_list = [
            # Stock frozen starting Jan 1, 2023
            Restriction(
                asset=stock_a,
                effective_date=pd.Timestamp('2023-01-01'),
                state=RESTRICTION_STATES.FROZEN
            ),
            # Stock unfrozen March 1, 2023
            Restriction(
                asset=stock_a,
                effective_date=pd.Timestamp('2023-03-01'),
                state=RESTRICTION_STATES.ALLOWED
            ),
        ]
        restrictions = HistoricalRestrictions(restrictions_list)

    Combining multiple restrictions::

        # Union of restrictions
        combined = static_restrictions | historical_restrictions
        # Asset is restricted if it appears in either list
"""
import abc
import operator
from collections import namedtuple
from enum import IntEnum
from functools import partial, reduce

import pandas as pd
from numpy import vectorize
from toolz import groupby

from rustybt.assets import Asset
from rustybt.utils.numpy_utils import vectorized_is_element

#: Named tuple representing a restriction with effective date
Restriction = namedtuple("Restriction", ["asset", "effective_date", "state"])

RESTRICTION_STATES = IntEnum(
    "RESTRICTION_STATES",
    [
        "ALLOWED",  # Asset can be traded
        "FROZEN",  # Asset trading is restricted
    ],
    start=0,
)


class Restrictions(metaclass=abc.ABCMeta):
    """Abstract base class for asset trading restrictions.

    Restrictions represent sets of assets that an algorithm is not allowed to
    trade, typically for compliance or risk management purposes. Subclasses
    implement specific restriction logic.

    The class supports combining restrictions using the | operator, allowing
    flexible composition of restriction policies.

    Example:
        Implementing a custom restriction::

            class MaxPriceRestrictions(Restrictions):
                def __init__(self, max_price):
                    self.max_price = max_price

                def is_restricted(self, assets, dt):
                    # Restrict assets above price threshold
                    if isinstance(assets, Asset):
                        price = data_portal.get_price(assets, dt)
                        return price > self.max_price
                    # Handle iterable of assets...
    """

    @abc.abstractmethod
    def is_restricted(self, assets, dt):
        """Check if asset(s) are restricted at the given time.

        Args:
            assets: Single Asset or iterable of Assets to check
            dt: Timestamp for the restriction query

        Returns:
            bool or pd.Series[bool]: True if restricted, False if allowed.
                Returns bool for single asset, Series for multiple assets.

        Example:
            Single asset check::

                is_blocked = restrictions.is_restricted(stock, pd.Timestamp('2023-01-01'))

            Multiple assets check::

                results = restrictions.is_restricted(
                    [stock_a, stock_b, stock_c],
                    pd.Timestamp('2023-01-01')
                )
                # Returns Series: {stock_a: False, stock_b: True, stock_c: False}
        """
        raise NotImplementedError("is_restricted")

    def __or__(self, other_restriction):
        """Combine this restriction with another using union semantics.

        Args:
            other_restriction: Another Restrictions instance

        Returns:
            _UnionRestrictions: Combined restriction where an asset is
                restricted if it's restricted in either restriction

        Example:
            Combining restriction lists::

                combined = static_list | historical_list
                # Asset is restricted if in either list

                triple = list1 | list2 | list3
                # Asset restricted if in any of the three lists
        """
        # If the right side is a _UnionRestrictions, defers to the
        # _UnionRestrictions implementation of `|`, which intelligently
        # flattens restricted lists
        if isinstance(other_restriction, _UnionRestrictions):
            return other_restriction | self
        return _UnionRestrictions([self, other_restriction])


class _UnionRestrictions(Restrictions):
    """Union of multiple restriction policies.

    This class combines multiple restrictions using OR logic: an asset is
    restricted if it's restricted by ANY of the sub-restrictions. This allows
    flexible composition of restriction policies.

    Args:
        sub_restrictions: Iterable of Restrictions objects (excluding nested
            _UnionRestrictions which are automatically flattened)

    Note:
        Consumers should not construct this class directly. Instead, use the
        | operator to combine restrictions::

            combined = restriction1 | restriction2 | restriction3

        NoRestrictions instances are automatically filtered out during
        construction.
    """

    def __new__(cls, sub_restrictions):
        # Filter out NoRestrictions and deal with resulting cases involving
        # one or zero sub_restrictions
        sub_restrictions = [r for r in sub_restrictions if not isinstance(r, NoRestrictions)]
        if len(sub_restrictions) == 0:
            return NoRestrictions()
        elif len(sub_restrictions) == 1:
            return sub_restrictions[0]

        new_instance = super(_UnionRestrictions, cls).__new__(cls)
        new_instance.sub_restrictions = sub_restrictions
        return new_instance

    def __or__(self, other_restriction):
        """Overrides the base implementation for combining two restrictions, of
        which the left side is a _UnionRestrictions.
        """
        # Flatten the underlying sub restrictions of _UnionRestrictions
        if isinstance(other_restriction, _UnionRestrictions):
            new_sub_restrictions = self.sub_restrictions + other_restriction.sub_restrictions
        else:
            new_sub_restrictions = self.sub_restrictions + [other_restriction]

        return _UnionRestrictions(new_sub_restrictions)

    def is_restricted(self, assets, dt):
        if isinstance(assets, Asset):
            return any(r.is_restricted(assets, dt) for r in self.sub_restrictions)

        return reduce(
            operator.or_,
            (r.is_restricted(assets, dt) for r in self.sub_restrictions),
        )


class NoRestrictions(Restrictions):
    """Empty restriction policy allowing all assets.

    This is a no-op restriction used as a default or placeholder when no
    actual restrictions are needed.

    Example:
        Using as default::

            restrictions = NoRestrictions()
            # All assets allowed
            restrictions.is_restricted(any_asset, any_dt)  # Always False
    """

    def is_restricted(self, assets, dt):
        """Always returns False (no restrictions).

        Args:
            assets: Single Asset or iterable of Assets
            dt: Timestamp (ignored)

        Returns:
            bool or pd.Series[bool]: Always False for single asset,
                Series of False for multiple assets
        """
        if isinstance(assets, Asset):
            return False
        return pd.Series(index=pd.Index(assets), data=False)


class StaticRestrictions(Restrictions):
    """Static restriction list that never changes over time.

    Assets in the restricted list are always forbidden, regardless of the
    query timestamp. This is useful for permanent blacklists or compliance
    restrictions that don't expire.

    Args:
        restricted_list: Iterable of Assets to restrict

    Example:
        Creating a permanent blacklist::

            blacklist = StaticRestrictions([stock_a, stock_b])

            # These assets are always restricted
            blacklist.is_restricted(stock_a, pd.Timestamp('2020-01-01'))  # True
            blacklist.is_restricted(stock_a, pd.Timestamp('2025-01-01'))  # True
            blacklist.is_restricted(stock_c, pd.Timestamp('2025-01-01'))  # False
    """

    def __init__(self, restricted_list):
        """Initialize static restrictions.

        Args:
            restricted_list: Iterable of Assets that are restricted
        """
        self._restricted_set = frozenset(restricted_list)

    def is_restricted(self, assets, dt):
        """Check if assets are in the restricted set.

        Args:
            assets: Single Asset or iterable of Assets
            dt: Timestamp (ignored, restrictions are time-independent)

        Returns:
            bool or pd.Series[bool]: True if restricted, False if allowed
        """
        if isinstance(assets, Asset):
            return assets in self._restricted_set
        return pd.Series(
            index=pd.Index(assets),
            data=vectorized_is_element(assets, self._restricted_set),
        )


class HistoricalRestrictions(Restrictions):
    """Time-dependent restrictions with effective dates.

    Each asset can have multiple restriction state changes over time, allowing
    simulation of real-world scenarios where restrictions are added or removed
    on specific dates.

    Args:
        restrictions: Iterable of Restriction namedtuples, each containing:
            - asset: The Asset being restricted
            - effective_date: Timestamp when the restriction takes effect
            - state: RESTRICTION_STATES.FROZEN or ALLOWED

    Example:
        Stock restricted in Q1 2023, then allowed again::

            from rustybt.finance.asset_restrictions import (
                HistoricalRestrictions,
                Restriction,
                RESTRICTION_STATES
            )

            restrictions = HistoricalRestrictions([
                # Freeze on Jan 1
                Restriction(
                    asset=stock_a,
                    effective_date=pd.Timestamp('2023-01-01'),
                    state=RESTRICTION_STATES.FROZEN
                ),
                # Unfreeze on Apr 1
                Restriction(
                    asset=stock_a,
                    effective_date=pd.Timestamp('2023-04-01'),
                    state=RESTRICTION_STATES.ALLOWED
                ),
            ])

            restrictions.is_restricted(stock_a, pd.Timestamp('2022-12-15'))  # False
            restrictions.is_restricted(stock_a, pd.Timestamp('2023-02-15'))  # True
            restrictions.is_restricted(stock_a, pd.Timestamp('2023-05-15'))  # False
    """

    def __init__(self, restrictions):
        """Initialize historical restrictions.

        Args:
            restrictions: Iterable of Restriction namedtuples with asset,
                effective_date, and state fields
        """
        # A dict mapping each asset to its restrictions, which are sorted by
        # ascending order of effective_date
        self._restrictions_by_asset = {
            asset: sorted(restrictions_for_asset, key=lambda x: x.effective_date)
            for asset, restrictions_for_asset in groupby(lambda x: x.asset, restrictions).items()
        }

    def is_restricted(self, assets, dt):
        """Check if assets are restricted at the given timestamp.

        Uses the most recent restriction state at or before the query timestamp.

        Args:
            assets: Single Asset or iterable of Assets
            dt: Timestamp for the restriction query

        Returns:
            bool or pd.Series[bool]: True if restricted at dt, False if allowed
        """
        if isinstance(assets, Asset):
            return self._is_restricted_for_asset(assets, dt)

        is_restricted = partial(self._is_restricted_for_asset, dt=dt)
        return pd.Series(
            index=pd.Index(assets),
            data=vectorize(is_restricted, otypes=[bool])(assets),
        )

    def _is_restricted_for_asset(self, asset, dt):
        """Check restriction state for a single asset at a given time.

        Args:
            asset: Asset to check
            dt: Timestamp for the query

        Returns:
            bool: True if FROZEN, False if ALLOWED
        """
        state = RESTRICTION_STATES.ALLOWED
        for r in self._restrictions_by_asset.get(asset, ()):
            r_effective_date = r.effective_date
            if r_effective_date.tzinfo is None:
                r_effective_date = r_effective_date.tz_localize(dt.tzinfo)
            if r_effective_date > dt:
                break
            state = r.state
        return state == RESTRICTION_STATES.FROZEN


class SecurityListRestrictions(Restrictions):
    """Dynamic restrictions based on a security list.

    Security lists are time-indexed collections of assets (e.g., index
    constituents, sector members) that change over time. Assets in the
    security list at a given timestamp are considered restricted.

    Args:
        security_list_by_dt: SecurityList object with time-indexed membership

    Example:
        Restricting based on S&P 500 membership::

            # Assume sp500_list provides current members at any date
            restrictions = SecurityListRestrictions(sp500_list)

            # Asset restricted if it was in S&P 500 on that date
            restrictions.is_restricted(stock, pd.Timestamp('2023-01-01'))

    Note:
        This is useful for simulating scenarios like "trade only non-index stocks"
        or "avoid trading index components to reduce market impact."
    """

    def __init__(self, security_list_by_dt):
        """Initialize security list restrictions.

        Args:
            security_list_by_dt: SecurityList object that provides
                current_securities(dt) method
        """
        self.current_securities = security_list_by_dt.current_securities

    def is_restricted(self, assets, dt):
        """Check if assets are in the security list at the given time.

        Args:
            assets: Single Asset or iterable of Assets
            dt: Timestamp for the query

        Returns:
            bool or pd.Series[bool]: True if asset is in the security list
                (and thus restricted), False otherwise
        """
        securities_in_list = self.current_securities(dt)
        if isinstance(assets, Asset):
            return assets in securities_in_list
        return pd.Series(
            index=pd.Index(assets),
            data=vectorized_is_element(assets, securities_in_list),
        )
