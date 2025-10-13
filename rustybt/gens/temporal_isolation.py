#
# Copyright 2025 RustyBT Contributors
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

"""
Temporal isolation validation to prevent lookahead bias.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class LookaheadError(Exception):
    """Raised when strategy attempts to access future data."""

    pass


class TemporalValidator:
    """
    Validates data access is temporally valid.

    Ensures strategies cannot access data from the future,
    preventing lookahead bias in backtesting.
    """

    def __init__(self, current_time: pd.Timestamp, debug_mode: bool = False):
        """
        Initialize temporal validator.

        Args:
            current_time: Current simulation time
            debug_mode: If True, log all data accesses for debugging
        """
        self.current_time = current_time
        self.debug_mode = debug_mode
        self.access_log: list[dict] = []

    def update_time(self, new_time: pd.Timestamp):
        """
        Update current time.

        Args:
            new_time: New simulation time

        Raises:
            ValueError: If new_time is before current_time (time travel)
        """
        if new_time < self.current_time:
            raise ValueError(
                f"Cannot move backwards in time from {self.current_time} to {new_time}"
            )
        self.current_time = new_time

    def validate_access(
        self, requested_time: pd.Timestamp, data_type: str, asset: Any | None = None
    ):
        """
        Validate data access does not look ahead.

        Args:
            requested_time: Time of data being requested
            data_type: Type of data being accessed (e.g., 'price', 'volume')
            asset: Optional asset identifier for logging

        Raises:
            LookaheadError: If requested_time is in the future
        """
        if requested_time > self.current_time:
            error_msg = (
                f"Attempted to access {data_type} at {requested_time}, "
                f"but current time is {self.current_time}"
            )
            if asset is not None:
                error_msg += f" for asset {asset}"

            raise LookaheadError(error_msg)

        # Log access in debug mode
        if self.debug_mode:
            access_record = {
                "current_time": self.current_time,
                "requested_time": requested_time,
                "data_type": data_type,
                "asset": asset,
            }
            self.access_log.append(access_record)
            logger.debug(
                "Data access: %s at %s (current: %s)",
                data_type,
                requested_time,
                self.current_time,
            )

    def get_access_log(self) -> list[dict]:
        """
        Get log of all data accesses (debug mode only).

        Returns:
            List of access records with timestamp, data_type, and asset
        """
        return self.access_log.copy()

    def clear_access_log(self):
        """Clear access log."""
        self.access_log.clear()
