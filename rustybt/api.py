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

# Note that part of the API is implemented in TradingAlgorithm as
# methods (e.g. order). These are added to this namespace via the
# decorator ``api_method`` inside of algorithm.py.
from .finance import cancel_policy, commission, execution, slippage
from .finance.asset_restrictions import (
    RESTRICTION_STATES,
    HistoricalRestrictions,
    Restriction,
    StaticRestrictions,
)
from .finance.cancel_policy import EODCancel, NeverCancel
from .finance.slippage import (
    FixedBasisPointsSlippage,
    FixedSlippage,
    VolumeShareSlippage,
)
from .utils import events, math_utils
from .utils.events import calendars, date_rules, time_rules

__all__ = [
    "RESTRICTION_STATES",
    "EODCancel",
    "FixedBasisPointsSlippage",
    "FixedSlippage",
    "HistoricalRestrictions",
    "NeverCancel",
    "Restriction",
    "StaticRestrictions",
    "VolumeShareSlippage",
    "calendars",
    "cancel_policy",
    "commission",
    "date_rules",
    "events",
    "execution",
    "math_utils",
    "slippage",
    "time_rules",
]


def __dir__():
    """Return all available attributes including dynamically registered API methods."""
    # Ensure algorithm module is loaded to trigger @api_method registration
    _ensure_algorithm_loaded()
    return list(globals().keys()) + __all__


def __getattr__(name):
    """Lazy load API methods from algorithm module when accessed."""
    # Ensure algorithm module is loaded to trigger @api_method registration
    _ensure_algorithm_loaded()

    # After algorithm loads, check if the attribute is now available
    if name in globals():
        return globals()[name]

    # If not found, raise AttributeError
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def _ensure_algorithm_loaded():
    """Ensure algorithm module is loaded to trigger @api_method decorator registration."""
    import sys

    if "rustybt.algorithm" not in sys.modules:
        from . import algorithm
