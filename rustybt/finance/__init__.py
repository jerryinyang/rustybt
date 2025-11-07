#
# Copyright 2013 Quantopian, Inc.
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

"""Financial modeling and trading infrastructure for rustybt.

This package provides the core financial modeling components for backtesting
trading algorithms, including:

- Order management and execution
- Position tracking and portfolio accounting
- Commission and slippage modeling
- Trading controls and risk management
- Transaction cost analysis

The finance module supports both traditional equities and modern asset classes
like cryptocurrencies, with comprehensive modeling of realistic market conditions.

Examples:
    Basic order execution with slippage and commission:

    >>> from rustybt.finance.slippage import FixedBasisPointsSlippage
    >>> from rustybt.finance.commission import PerShare
    >>> from rustybt import run_algorithm
    >>>
    >>> results = run_algorithm(
    ...     start=start_date,
    ...     end=end_date,
    ...     initialize=initialize,
    ...     handle_data=handle_data,
    ...     slippage=FixedBasisPointsSlippage(basis_points=5.0),
    ...     commission=PerShare(cost=0.001),
    ... )
"""

from . import execution, trading

__all__ = ["execution", "trading"]
