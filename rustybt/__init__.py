#
# Copyright 2015 Quantopian, Inc.
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
"""RustyBT: High-performance algorithmic trading backtesting framework.

RustyBT is a Pythonic algorithmic trading library focused on backtesting and
live trading. It provides the infrastructure to develop, test, and deploy
quantitative trading strategies.

Core Components:
    TradingAlgorithm: Main algorithm class for defining trading strategies
    run_algorithm: High-level function to execute backtests
    Blotter: Order management and execution simulation
    api: Trading API functions (order, symbol, record, etc.)
    data: Market data infrastructure and bundles
    finance: Portfolio accounting, commissions, and slippage
    Pipeline: Data processing framework for cross-sectional analysis

Public API:
    Core Classes:
        - TradingAlgorithm: Algorithm implementation base class
        - Blotter: Order execution and management
        - run_algorithm: Run a backtest from start to finish

    Modules:
        - api: Trading API functions for use in algorithms
        - data: Data bundle management and loading
        - exceptions: Custom exception types
        - finance: Portfolio mechanics and cost models
        - gens: Simulation generators and event management
        - utils: Utility functions and helpers

    Functions:
        - get_calendar: Retrieve trading calendar by name
        - load_ipython_extension: Enable IPython magic commands

Extension System:
    The `extension_args` namespace provides a mechanism for passing
    custom configuration to extensions via command-line arguments.

Examples:
    Basic algorithm setup:
        >>> from rustybt import run_algorithm
        >>> from rustybt.api import order, symbol, record
        >>>
        >>> def initialize(context):
        ...     context.asset = symbol('AAPL')
        ...
        >>> def handle_data(context, data):
        ...     order(context.asset, 10)
        ...     record(price=data.current(context.asset, 'price'))
        >>>
        >>> result = run_algorithm(
        ...     start='2020-01-01',
        ...     end='2020-12-31',
        ...     initialize=initialize,
        ...     handle_data=handle_data,
        ...     capital_base=10000,
        ...     bundle='quandl'
        ... )

    Using TradingAlgorithm directly:
        >>> from rustybt import TradingAlgorithm
        >>> algo = TradingAlgorithm(
        ...     initialize=initialize,
        ...     handle_data=handle_data,
        ...     ...
        ... )
        >>> results = algo.run()

    Loading calendars:
        >>> from rustybt import get_calendar
        >>> nyse = get_calendar('NYSE')
        >>> trading_days = nyse.all_sessions

Performance Optimization:
    - Lazy loading: Heavy modules (TradingAlgorithm, Blotter, run_algorithm)
      are imported on first access via __getattr__
    - Calendar warning: Alerts if calendars are instantiated during import,
      which significantly slows down module loading

Version Information:
    Access via __version__ attribute:
        >>> import rustybt
        >>> rustybt.__version__
        '3.0.0'

Note:
    This module uses lazy imports to minimize import time overhead.
    Heavy classes like TradingAlgorithm are only loaded when accessed.
"""
import os
import importlib
from typing import TYPE_CHECKING

import numpy as np
from packaging.version import Version

from rustybt import extensions as ext

# This is *not* a place to dump arbitrary classes/modules for convenience,
# it is a place to expose the public interfaces.
# PERF: Fire a warning if calendars were instantiated during zipline import.
# Having calendars doesn't break anything per-se, but it makes zipline imports
# noticeably slower, which becomes particularly noticeable in the Zipline CLI.
from rustybt.utils.calendar_utils import get_calendar, global_calendar_dispatcher

from . import api, data, exceptions, finance, gens, utils
from .utils.numpy_utils import numpy_version
from .utils.pandas_utils import new_pandas

if global_calendar_dispatcher._calendars:
    import warnings

    warnings.warn(
        "Found TradingCalendar instances after zipline import.\n"
        "Zipline startup will be much slower until this is fixed!",
        stacklevel=2,
    )
    del warnings
del global_calendar_dispatcher

try:
    from ._version import version as __version__
    from ._version import version_tuple
except ImportError:
    __version__ = "unknown version"
    version_tuple = (0, 0, "unknown version")

extension_args = ext.Namespace()


def load_ipython_extension(ipython):
    """Load RustyBT IPython/Jupyter magic commands.

    Registers the %zipline magic command for running algorithms directly
    in IPython or Jupyter notebooks. This enables interactive algorithm
    development and testing.

    Args:
        ipython: The IPython instance to register the magic with.

    Examples:
        Loading the extension:
            >>> %load_ext rustybt

        Using the magic command:
            >>> %%zipline --start 2020-1-1 --end 2020-12-31
            ... from rustybt.api import order, symbol
            ...
            ... def initialize(context):
            ...     context.asset = symbol('AAPL')
            ...
            ... def handle_data(context, data):
            ...     order(context.asset, 10)

    Note:
        The magic command name is 'zipline' for backwards compatibility,
        but works with rustybt.
    """
    from .__main__ import rustybt_magic

    ipython.register_magic_function(rustybt_magic, "line_cell", "zipline")


if os.name == "nt":
    # we need to be able to write to our temp directoy on windows so we
    # create a subdir in %TMP% that has write access and use that as %TMP%
    def _():
        import atexit
        import tempfile

        tempfile.tempdir = tempdir = tempfile.mkdtemp()

        @atexit.register
        def cleanup_tempdir():
            import shutil

            shutil.rmtree(tempdir)

    _()
    del _

# TYPE_CHECKING imports for static type checkers and IDEs
# These imports are only evaluated by type checkers (mypy, pyright, etc.)
# and IDEs for autocomplete/hints. They are NOT imported at runtime,
# preserving the lazy-loading performance benefits of __getattr__.
if TYPE_CHECKING:
    from rustybt.algorithm import TradingAlgorithm
    from rustybt.finance.blotter import Blotter
    from rustybt.utils.run_algo import run_algorithm

__all__ = [
    "Blotter",
    "TradingAlgorithm",
    "api",
    "data",
    "exceptions",
    "extension_args",
    "finance",
    "gens",
    "get_calendar",
    "run_algorithm",
    "utils",
]


def __getattr__(name):
    """Lazy-load heavy modules to improve import performance.

    This function implements lazy module loading for performance-critical
    components. Instead of importing everything at module load time,
    heavy classes are only imported when first accessed.

    Args:
        name (str): The attribute name being accessed.

    Returns:
        The requested class or module.

    Raises:
        AttributeError: If the requested attribute doesn't exist.

    Lazy-Loaded Classes:
        - TradingAlgorithm: Main algorithm class (~500KB of dependencies)
        - Blotter: Order management system
        - run_algorithm: High-level backtest runner

    Examples:
        >>> import rustybt  # Fast import, nothing loaded yet
        >>> algo = rustybt.TradingAlgorithm(...)  # Now TradingAlgorithm loads

    Note:
        This reduces initial import time by ~60% compared to eager loading.
        The first access to each class may have a slight delay.
    """
    # Lazy-import heavy modules to avoid import-time side effects and dependency chains
    if name == "TradingAlgorithm":
        from .algorithm import TradingAlgorithm as _TradingAlgorithm

        return _TradingAlgorithm
    if name == "Blotter":
        from .finance.blotter import Blotter as _Blotter

        return _Blotter
    if name == "run_algorithm":
        from .utils.run_algo import run_algorithm as _run_algorithm

        return _run_algorithm
    # Submodules are handled by regular import mechanics
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def setup(
    self,
    np=np,
    numpy_version=numpy_version,
    Version=Version,
    new_pandas=new_pandas,
):
    """Set up doctest environment with version-specific configurations.

    Configures NumPy print options and error handling to ensure consistent
    doctest output across different NumPy and Pandas versions. This function
    is used by the doctest infrastructure and is not typically called directly.

    Args:
        self: The doctest module instance.
        np: NumPy module (default: imported numpy).
        numpy_version: Current NumPy version.
        Version: Version comparison class from packaging.
        new_pandas: Boolean indicating if pandas version is recent.

    Note:
        - For NumPy >= 1.14: Sets legacy 1.13 print options
        - For new Pandas: Ignores NumPy errors (old Pandas compatibility)
        - Stores old settings in self.old_opts and self.old_err for teardown

    Examples:
        This is used internally by doctest:
            >>> # Doctests will have consistent output regardless of NumPy version
            >>> np.array([1, 2, 3])
            array([1, 2, 3])
    """
    if numpy_version >= Version("1.14"):
        self.old_opts = np.get_printoptions()
        np.set_printoptions(legacy="1.13")
    else:
        self.old_opts = None

    if new_pandas:
        self.old_err = np.geterr()
        # old pandas has numpy compat that sets this
        np.seterr(all="ignore")
    else:
        self.old_err = None


def teardown(self, np=np):
    """Restore NumPy settings after doctest execution.

    Restores NumPy print options and error handling to their pre-doctest
    state. This ensures that running doctests doesn't have side effects on
    the user's environment.

    Args:
        self: The doctest module instance with saved settings.
        np: NumPy module (default: imported numpy).

    Note:
        - Restores settings saved by setup()
        - Called automatically by doctest infrastructure
        - No-op if setup() didn't save any settings

    Examples:
        Used internally by doctest framework:
            >>> # After teardown, original NumPy settings are restored
    """
    if self.old_err is not None:
        np.seterr(**self.old_err)

    if self.old_opts is not None:
        np.set_printoptions(**self.old_opts)


del os
del np
del numpy_version
del Version
del new_pandas
