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

"""Futures contract roll finding and continuous contract management.

This module provides infrastructure for determining when to "roll" from one futures
contract to the next in a continuous futures chain. Rolling is essential for creating
continuous price series from a sequence of individual futures contracts that expire
at different times.

Roll Strategies:
    Calendar Rolls:
        Switch contracts based on fixed calendar dates (typically the auto_close_date).
        Simple and predictable, but may not reflect actual market behavior.

    Volume Rolls:
        Switch contracts when trading volume shifts from the front contract to the back
        contract. More accurately reflects market participant behavior, but requires
        volume data and more complex logic.

Key Classes:
    RollFinder: Abstract base class defining the roll finding interface
    CalendarRollFinder: Implements calendar-based rolling
    VolumeRollFinder: Implements volume-based rolling

Continuous Futures:
    Roll finders are primarily used with ContinuousFuture assets to maintain a
    consistent view of a futures contract chain over time. The roll finder determines
    which individual contract should be considered "active" on any given date.

Examples:
    Calendar-based rolling:
        >>> from rustybt.assets.roll_finder import CalendarRollFinder
        >>> from rustybt.assets import AssetFinder
        >>> from rustybt.utils.calendar_utils import get_calendar
        >>> finder = AssetFinder("sqlite:///assets.db")
        >>> calendar = get_calendar("NYSE")
        >>> roll_finder = CalendarRollFinder(calendar, finder)
        >>> # Get the active contract on a specific date
        >>> import pandas as pd
        >>> active = roll_finder.get_contract_center(
        ...     root_symbol='CL',
        ...     dt=pd.Timestamp('2020-06-15'),
        ...     offset=0  # 0 for front month, 1 for next month, etc.
        ... )

    Volume-based rolling with a session reader:
        >>> from rustybt.assets.roll_finder import VolumeRollFinder
        >>> # Requires a session_reader with volume data
        >>> vol_roll_finder = VolumeRollFinder(calendar, finder, session_reader)
        >>> active = vol_roll_finder.get_contract_center('ES', pd.Timestamp('2020-06-15'), 0)

    Get roll schedule for a date range:
        >>> rolls = roll_finder.get_rolls(
        ...     root_symbol='CL',
        ...     start=pd.Timestamp('2020-01-01'),
        ...     end=pd.Timestamp('2020-12-31'),
        ...     offset=0
        ... )
        >>> # Returns list of (sid, roll_date) tuples

See Also:
    rustybt.assets.continuous_futures: ContinuousFuture asset type
    rustybt.data: Data readers that use roll finders

Notes:
    - Volume-based rolling requires historical volume data
    - Roll dates can vary by offset (front month vs. second month, etc.)
    - The ROLL_DAYS_FOR_CURRENT_CONTRACT constant (90 days) is used by volume
      roll finder to avoid flip-flopping between contracts
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rustybt.assets import AssetFinder
    from rustybt.utils.calendar_utils import TradingCalendar
else:
    AssetFinder = Any
    TradingCalendar = Any

# Number of days over which to compute rolls when finding the current contract
# for a volume-rolling contract chain. For more details on why this is needed,
# see `VolumeRollFinder.get_contract_center`.
ROLL_DAYS_FOR_CURRENT_CONTRACT = 90


class RollFinder(ABC):
    """Abstract base class for calculating when futures contracts roll.

    A roll finder determines which contract in a futures chain is considered "active"
    at any given time. Subclasses must implement the contract selection logic by
    defining the `_active_contract` method.

    Attributes:
        asset_finder: AssetFinder instance for contract lookup.
        trading_calendar: TradingCalendar for session calculations.
    """

    # Subclasses must set these attributes
    asset_finder: "AssetFinder"  # type: ignore[misc]
    trading_calendar: "TradingCalendar"

    @abstractmethod
    def _active_contract(self, oc, front, back, dt):
        raise NotImplementedError

    def _get_active_contract_at_offset(self, root_symbol, dt, offset):
        """For the given root symbol, find the contract that is considered active
        on a specific date at a specific offset.
        """
        oc = self.asset_finder.get_ordered_contracts(root_symbol)
        session = self.trading_calendar.minute_to_session(dt)
        front = oc.contract_before_auto_close(session.value)
        back = oc.contract_at_offset(front, 1, dt.value)
        if back is None:
            return front
        primary = self._active_contract(oc, front, back, session)
        return oc.contract_at_offset(primary, offset, session.value)

    def get_contract_center(self, root_symbol, dt, offset):
        """Get the active contract for a futures chain at a specific date.

        Determines which individual futures contract should be considered "active"
        for the given root symbol and date, accounting for the specified offset from
        the primary (front) contract.

        Args:
            root_symbol: The futures root symbol (e.g., 'CL', 'ES', 'NG').
            dt: The date/time for which to find the active contract.
            offset: Contract offset from the front month. 0 = front month (nearest
                expiration), 1 = second month, 2 = third month, etc.

        Returns:
            Future: The active futures contract at the given date and offset.

        Examples:
            Get front month contract:
                >>> active = roll_finder.get_contract_center('CL', pd.Timestamp('2020-06-15'), 0)

            Get second month contract:
                >>> next_month = roll_finder.get_contract_center('CL', pd.Timestamp('2020-06-15'), 1)
        """
        return self._get_active_contract_at_offset(root_symbol, dt, offset)

    def get_rolls(self, root_symbol, start, end, offset):
        """Get the roll schedule for a futures chain over a date range.

        Calculates when to "roll" from one contract to the next in a continuous
        futures chain, returning a list of (sid, roll_date) tuples that define
        which contract is active and when to switch to the next one.

        Args:
            root_symbol: The futures root symbol for which to calculate rolls.
            start: Start date of the date range.
            end: End date of the date range.
            offset: Contract offset from the primary. 0 for front month, 1 for
                second month, etc.

        Returns:
            list[tuple[int, pd.Timestamp or None]]: List of (sid, roll_date) tuples where:
                - sid: The contract sid that is active
                - roll_date: The date on which to roll to the next contract, or None
                  for the last contract in the range (no subsequent roll needed)

        Examples:
            Get front month roll schedule for a year:
                >>> rolls = roll_finder.get_rolls(
                ...     root_symbol='CL',
                ...     start=pd.Timestamp('2020-01-01'),
                ...     end=pd.Timestamp('2020-12-31'),
                ...     offset=0
                ... )
                >>> for sid, roll_date in rolls:
                ...     print(f"Contract {sid} until {roll_date}")
        """
        oc = self.asset_finder.get_ordered_contracts(root_symbol)
        front = self._get_active_contract_at_offset(root_symbol, end, 0)
        back = oc.contract_at_offset(front, 1, end.value)
        if back is not None:
            end_session = self.trading_calendar.minute_to_session(end)
            first = self._active_contract(oc, front, back, end_session)
        else:
            first = front
        first_contract = oc.sid_to_contract[first]
        rolls = [((first_contract >> offset).contract.sid, None)]
        tc = self.trading_calendar
        sessions = tc.sessions_in_range(tc.minute_to_session(start), tc.minute_to_session(end))
        freq = sessions.freq
        if first == front:
            # This is a bit tricky to grasp. Once we have the active contract
            # on the given end date, we want to start walking backwards towards
            # the start date and checking for rolls. For this, we treat the
            # previous month's contract as the 'first' contract, and the
            # contract we just found to be active as the 'back'. As we walk
            # towards the start date, if the 'back' is no longer active, we add
            # that date as a roll.
            curr = first_contract << 1
        else:
            curr = first_contract << 2
        session = sessions[-1]

        start = start.tz_localize(None)

        while session > start and curr is not None:
            front = curr.contract.sid
            back = rolls[0][0]
            prev_c = curr.prev
            while session > start:
                prev = (session - freq).tz_localize(None)
                if prev_c is not None:
                    if prev < prev_c.contract.auto_close_date:
                        break
                if back != self._active_contract(oc, front, back, prev):
                    # TODO: Instead of listing each contract with its roll date
                    # as tuples, create a series which maps every day to the
                    # active contract on that day.
                    rolls.insert(0, ((curr >> offset).contract.sid, session))
                    break
                session = prev
            curr = curr.prev
            if curr is not None:
                session = min(session, curr.contract.auto_close_date + freq)

        return rolls


class CalendarRollFinder(RollFinder):
    """Roll finder using calendar-based contract switching.

    Determines active contracts based solely on the contract's auto_close_date,
    switching to the next contract when the current one reaches its auto close date.
    This is the simplest roll strategy and doesn't require any price or volume data.

    The calendar roll strategy is deterministic and easy to understand, but may not
    reflect actual market behavior where participants often roll before the official
    close date.

    Args:
        trading_calendar: TradingCalendar for date/session calculations.
        asset_finder: AssetFinder for contract lookup and metadata.

    Examples:
        Create a calendar roll finder:
            >>> from rustybt.assets.roll_finder import CalendarRollFinder
            >>> from rustybt.assets import AssetFinder
            >>> from rustybt.utils.calendar_utils import get_calendar
            >>> finder = AssetFinder("sqlite:///assets.db")
            >>> calendar = get_calendar("NYSE")
            >>> roll_finder = CalendarRollFinder(calendar, finder)

        Find active contract:
            >>> active = roll_finder.get_contract_center('CL', pd.Timestamp('2020-06-15'), 0)
    """

    def __init__(self, trading_calendar, asset_finder):
        """Initialize a CalendarRollFinder.

        Args:
            trading_calendar: Trading calendar for session calculations.
            asset_finder: Asset finder for contract lookups.
        """
        self.trading_calendar = trading_calendar
        self.asset_finder = asset_finder

    def _active_contract(self, oc, front, back, dt):
        contract = oc.sid_to_contract[front].contract
        auto_close_date = contract.auto_close_date
        auto_closed = dt >= auto_close_date
        return back if auto_closed else front


class VolumeRollFinder(RollFinder):
    """Roll finder using volume-based contract switching.

    Determines active contracts by tracking when trading volume shifts from the
    front contract to the back contract. This better reflects actual market behavior
    where traders migrate to the next contract before the official close date.

    The volume roll strategy uses a grace period near the auto_close_date to detect
    and lock in volume transitions, preventing flip-flopping between contracts when
    volumes are close.

    Attributes:
        GRACE_DAYS: Number of days before auto_close_date to check for volume shifts.
            Default is 7 days.

    Args:
        trading_calendar: TradingCalendar for date/session calculations.
        asset_finder: AssetFinder for contract lookup and metadata.
        session_reader: Data reader providing historical volume data.

    Examples:
        Create a volume roll finder:
            >>> from rustybt.assets.roll_finder import VolumeRollFinder
            >>> from rustybt.assets import AssetFinder
            >>> from rustybt.utils.calendar_utils import get_calendar
            >>> from rustybt.data import load_session_reader
            >>> finder = AssetFinder("sqlite:///assets.db")
            >>> calendar = get_calendar("NYSE")
            >>> reader = load_session_reader()
            >>> vol_roll_finder = VolumeRollFinder(calendar, finder, reader)

        Find volume-based active contract:
            >>> active = vol_roll_finder.get_contract_center('ES', pd.Timestamp('2020-06-15'), 0)

    Notes:
        - Requires historical volume data in the session_reader
        - More computationally expensive than calendar rolling
        - Better reflects actual market roll behavior
    """

    GRACE_DAYS = 7

    def __init__(self, trading_calendar, asset_finder, session_reader):
        """Initialize a VolumeRollFinder.

        Args:
            trading_calendar: Trading calendar for session calculations.
            asset_finder: Asset finder for contract lookups.
            session_reader: Session data reader with volume data.
        """
        self.trading_calendar = trading_calendar
        self.asset_finder = asset_finder
        self.session_reader = session_reader

    def _active_contract(self, oc, front, back, dt):
        r"""
        Return the active contract based on the previous trading day's volume.

        In the rare case that a double volume switch occurs we treat the first
        switch as the roll. Take the following case for example:

        | +++++             _____
        |      +   __      /       <--- 'G'
        |       ++/++\++++/++
        |       _/    \__/   +
        |      /              +
        | ____/                +   <--- 'F'
        |_________|__|___|________
                  a  b   c         <--- Switches

        We should treat 'a' as the roll date rather than 'c' because from the
        perspective of 'a', if a switch happens and we are pretty close to the
        auto-close date, we would probably assume it is time to roll. This
        means that for every date after 'a', `data.current(cf, 'contract')`
        should return the 'G' contract.
        """
        front_contract = oc.sid_to_contract[front].contract
        back_contract = oc.sid_to_contract[back].contract

        tc = self.trading_calendar
        trading_day = tc.day
        prev = dt - trading_day
        get_value = self.session_reader.get_value

        # If the front contract is past its auto close date it cannot be the
        # active contract, so return the back contract. Similarly, if the back
        # contract has not even started yet, just return the front contract.
        # The reason for using 'prev' to see if the contracts are alive instead
        # of using 'dt' is because we need to get each contract's volume on the
        # previous day, so we need to make sure that each contract exists on
        # 'prev' in order to call 'get_value' below.
        if (
            dt > min(front_contract.auto_close_date, front_contract.end_date)
            or front_contract.start_date > prev
        ):
            return back
        elif (
            dt > min(back_contract.auto_close_date, back_contract.end_date)
            or back_contract.start_date > prev
        ):
            return front

        front_vol = get_value(front, prev, "volume")
        back_vol = get_value(back, prev, "volume")
        if back_vol > front_vol:
            return back

        gap_start = max(
            back_contract.start_date,
            front_contract.auto_close_date - (trading_day * self.GRACE_DAYS),
        )
        gap_end = prev - trading_day
        if dt < gap_start:
            return front

        # If we are within `self.GRACE_DAYS` of the front contract's auto close
        # date, and a volume flip happened during that period, return the back
        # contract as the active one.
        sessions = tc.sessions_in_range(
            tc.minute_to_session(gap_start),
            tc.minute_to_session(gap_end),
        )
        for session in sessions:
            front_vol = get_value(front, session, "volume")
            back_vol = get_value(back, session, "volume")
            if back_vol > front_vol:
                return back
        return front

    def get_contract_center(self, root_symbol, dt, offset):
        """Get the volume-based active contract with anti-flip-flop protection.

        Extends the base implementation by using roll schedule information over a
        90-day window to prevent flip-flopping between contracts when volumes are
        similar. This provides more stable contract selection compared to naive
        volume comparison.

        Args:
            root_symbol: The futures root symbol (e.g., 'CL', 'ES', 'NG').
            dt: The date/time for which to find the active contract.
            offset: Contract offset from the front month. 0 = front month,
                1 = second month, etc.

        Returns:
            Future: The active futures contract based on volume patterns.

        Notes:
            Uses a ROLL_DAYS_FOR_CURRENT_CONTRACT (90 day) window to incorporate
            roll schedule context, preventing daily flip-flopping between contracts
            with similar volumes.
        """
        # When determining the center contract on a specific day using volume
        # rolls, simply picking the contract with the highest volume could
        # cause flip-flopping between active contracts each day if the front
        # and back contracts are close in volume. Therefore, information about
        # the surrounding rolls is required. The `get_rolls` logic prevents
        # contracts from being considered active once they have rolled, so
        # incorporating that logic here prevents flip-flopping.
        day = self.trading_calendar.day
        end_date = min(
            dt + (ROLL_DAYS_FOR_CURRENT_CONTRACT * day),
            self.session_reader.last_available_dt.tz_localize(dt.tzinfo),
        )
        rolls = self.get_rolls(
            root_symbol=root_symbol,
            start=dt,
            end=end_date,
            offset=offset,
        )
        sid, acd = rolls[0]
        return self.asset_finder.retrieve_asset(sid)
