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
"""Order cancellation policies for automatic order management.

This module provides policy classes that determine when open orders should be
automatically cancelled by the simulation engine. Cancellation policies help
simulate realistic broker behavior where orders may not persist indefinitely.

The two main policies are:
- EODCancel: Cancel all unfilled orders at end of day (realistic for most brokers)
- NeverCancel: Keep orders open indefinitely (useful for testing)

Example:
    Using end-of-day cancellation in minutely mode::

        from rustybt.finance.cancel_policy import EODCancel

        blotter = SimulationBlotter(
            cancel_policy=EODCancel(warn_on_cancel=True)
        )

    Disabling automatic cancellation::

        from rustybt.finance.cancel_policy import NeverCancel

        blotter = SimulationBlotter(
            cancel_policy=NeverCancel()
        )
"""
import abc
from abc import abstractmethod

from rustybt.gens.sim_engine import SESSION_END


class CancelPolicy(metaclass=abc.ABCMeta):
    """Abstract base class for order cancellation policies.

    Cancellation policies determine when open orders should be automatically
    cancelled by the simulation engine. Subclasses implement specific
    cancellation rules based on simulation events.

    Example:
        Implementing a custom cancellation policy::

            class CancelAfterNBars(CancelPolicy):
                def __init__(self, n_bars, warn_on_cancel=True):
                    self.n_bars = n_bars
                    self.warn_on_cancel = warn_on_cancel
                    self.bar_count = 0

                def should_cancel(self, event):
                    if event == BAR:
                        self.bar_count += 1
                        return self.bar_count >= self.n_bars
                    return False
    """

    @abstractmethod
    def should_cancel(self, event):
        """Determine if open orders should be cancelled for the given event.

        Args:
            event: Simulation event type, one of:
                - BAR: New price bar
                - DAY_START: Start of trading day
                - SESSION_END: End of trading session
                - MINUTE_END: End of minute bar

        Returns:
            bool: True if all open orders should be cancelled, False otherwise

        Note:
            This method is called by the blotter on each simulation event.
            Returning True will cancel ALL open orders across all assets.
        """
        pass


class EODCancel(CancelPolicy):
    """Cancel all open orders at end of trading day.

    This policy mimics typical broker behavior where day orders (as opposed to
    Good-Til-Cancelled orders) automatically expire at market close. This is
    the most realistic cancellation policy for minutely simulations.

    Args:
        warn_on_cancel: Whether to log warnings when orders are cancelled
            (default: True)

    Example:
        End-of-day cancellation with warnings::

            policy = EODCancel(warn_on_cancel=True)

            # In the blotter, orders placed at 9:30 AM
            # will be cancelled at 4:00 PM if unfilled

        Silent end-of-day cancellation::

            policy = EODCancel(warn_on_cancel=False)

    Note:
        Currently only applied to minutely simulations. Daily simulations
        process all orders in a single bar, so cancellation is not applicable.
    """

    def __init__(self, warn_on_cancel=True):
        """Initialize end-of-day cancel policy.

        Args:
            warn_on_cancel: Log warnings for cancelled orders (default: True)
        """
        self.warn_on_cancel = warn_on_cancel

    def should_cancel(self, event):
        """Cancel orders at session end.

        Args:
            event: Simulation event

        Returns:
            bool: True if event is SESSION_END, False otherwise
        """
        return event == SESSION_END


class NeverCancel(CancelPolicy):
    """Never automatically cancel orders.

    This policy keeps all orders open indefinitely until they are filled,
    explicitly cancelled by the algorithm, or the simulation ends. Useful
    for testing or strategies that rely on Good-Til-Cancelled (GTC) orders.

    Example:
        Orders remain open across multiple days::

            policy = NeverCancel()

            # Order placed Monday at $100 limit
            # If price never reaches $100, order stays open
            # through Tuesday, Wednesday, etc. until filled

    Note:
        While useful for testing, this is less realistic than EODCancel for
        most trading scenarios. Real brokers typically expire day orders at
        market close unless explicitly marked as GTC.
    """

    def __init__(self):
        """Initialize never-cancel policy.

        Note:
            Sets warn_on_cancel=False since orders are never cancelled.
        """
        self.warn_on_cancel = False

    def should_cancel(self, event):
        """Never cancel orders.

        Args:
            event: Simulation event (ignored)

        Returns:
            bool: Always returns False
        """
        return False
