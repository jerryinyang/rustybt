#
# Copyright 2018 Quantopian, Inc.
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

"""Order management and blotter infrastructure.

This module provides the blotter system for managing orders throughout their lifecycle,
from placement through execution and cancellation. The blotter is responsible for:

- Order placement and validation
- Order lifecycle management (open, filled, canceled, rejected)
- Integration with slippage and commission models
- Transaction generation from order fills
- Advanced order types (OCO, bracket orders, trailing stops)

The base Blotter class defines the interface, while SimulationBlotter provides
the concrete implementation used during backtesting simulations.

Examples:
    Creating a blotter with custom slippage and commission:

    >>> from rustybt.finance.blotter import SimulationBlotter
    >>> from rustybt.finance.slippage import FixedBasisPointsSlippage
    >>> from rustybt.finance.commission import PerShare
    >>>
    >>> blotter = SimulationBlotter(
    ...     equity_slippage=FixedBasisPointsSlippage(basis_points=5.0),
    ...     equity_commission=PerShare(cost=0.001),
    ... )
"""

from .blotter import Blotter
from .simulation_blotter import SimulationBlotter

__all__ = [
    "Blotter",
    "SimulationBlotter",
]
