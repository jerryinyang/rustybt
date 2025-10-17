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
Notebook utilities for async execution and progress tracking.

Provides:
- Async wrapper for backtests in Jupyter notebooks
- Progress bars for long-running operations
- IPython kernel event loop compatibility
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

import pandas as pd
from tqdm.auto import tqdm

try:
    import nest_asyncio

    NEST_ASYNCIO_AVAILABLE = True
except ImportError:
    NEST_ASYNCIO_AVAILABLE = False

try:
    from IPython import get_ipython

    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False


def setup_notebook() -> None:
    """Setup notebook environment for RustyBT.

    This function:
    - Enables nest_asyncio for async/await support in Jupyter
    - Configures pandas display options for better DataFrame rendering
    - Sets up progress bar widgets for Jupyter

    Call this at the beginning of your notebook:
        >>> from rustybt.analytics import setup_notebook
        >>> setup_notebook()

    Raises:
        ImportError: If required packages are not installed
    """
    if not IPYTHON_AVAILABLE:
        raise ImportError(
            "IPython not found. This function is intended for Jupyter notebooks. "
            "Install with: pip install ipython"
        )

    if not NEST_ASYNCIO_AVAILABLE:
        raise ImportError("nest-asyncio not found. Install with: pip install nest-asyncio")

    # Enable nested event loops for async support
    nest_asyncio.apply()

    # Configure pandas display options
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_rows", 100)
    pd.set_option("display.width", None)
    pd.set_option("display.float_format", "{:.6f}".format)

    # Check if we're in a Jupyter notebook
    ipython = get_ipython()
    if ipython is not None:
        # Load tqdm extension for better progress bars
        ipython.run_line_magic("load_ext", "autoreload")
        ipython.run_line_magic("autoreload", "2")

    print("✅ Notebook environment configured successfully")
    print("   - Async/await support enabled")
    print("   - Pandas display options optimized")
    print("   - Progress bars configured")


async def async_backtest(
    algorithm: Any,
    data_portal: Any = None,
    show_progress: bool = True,
    progress_desc: str = "Running backtest",
) -> pd.DataFrame:
    """Run backtest asynchronously with progress tracking.

    This function wraps the standard backtest execution to support
    async/await syntax in Jupyter notebooks.

    Args:
        algorithm: TradingAlgorithm instance to run
        data_portal: Optional DataPortal instance
        show_progress: Whether to show progress bar
        progress_desc: Description for progress bar

    Returns:
        DataFrame with backtest results

    Example:
        >>> from rustybt.analytics import async_backtest, setup_notebook
        >>> setup_notebook()
        >>> results = await async_backtest(my_algorithm)

    Note:
        Make sure to call setup_notebook() before using this function.
    """
    if not NEST_ASYNCIO_AVAILABLE:
        raise ImportError(
            "nest-asyncio required for async backtests. Install with: pip install nest-asyncio"
        )

    # Ensure nest_asyncio is applied
    try:
        nest_asyncio.apply()
    except RuntimeError:
        pass  # Already applied

    # Run backtest in thread pool to avoid blocking
    loop = asyncio.get_event_loop()

    if show_progress:
        with tqdm(total=100, desc=progress_desc) as pbar:
            # Update progress at intervals
            def run_with_progress():
                pbar.update(10)  # Initial progress
                result = algorithm.run(data_portal=data_portal)
                pbar.update(90)  # Complete
                return result

            result = await loop.run_in_executor(None, run_with_progress)
    else:
        result = await loop.run_in_executor(None, algorithm.run, data_portal)

    return result


def with_progress(
    desc: str | None = None,
    total: int | None = None,
    unit: str = "it",
) -> Callable:
    """Decorator to add progress bar to any function.

    Args:
        desc: Description for progress bar
        total: Total number of iterations (if known)
        unit: Unit name for progress

    Returns:
        Decorated function with progress tracking

    Example:
        >>> @with_progress(desc="Processing data", total=100)
        ... def process_data(items):
        ...     for item in items:
        ...         # Process item
        ...         yield item
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Determine if function is generator
            result = func(*args, **kwargs)

            if hasattr(result, "__iter__") and not isinstance(result, (str, bytes, pd.DataFrame)):
                # Wrap iterable with tqdm
                return tqdm(result, desc=desc or func.__name__, total=total, unit=unit)
            else:
                # Not iterable, return as-is
                return result

        return wrapper

    return decorator


class ProgressCallback:
    """Progress tracking callback for backtest execution.

    This class provides hooks for tracking backtest progress
    and displaying it in a Jupyter notebook.

    Example:
        >>> progress = ProgressCallback(total_days=252)
        >>> # Use in backtest execution
        >>> for day in backtest_days:
        ...     progress.update(1)
        ...     # Execute trading day
    """

    def __init__(self, total: int, desc: str = "Backtest Progress", unit: str = "days"):
        """Initialize progress callback.

        Args:
            total: Total number of items to process
            desc: Description for progress bar
            unit: Unit name for progress
        """
        self.pbar = tqdm(total=total, desc=desc, unit=unit)

    def update(self, n: int = 1) -> None:
        """Update progress by n steps.

        Args:
            n: Number of steps to advance
        """
        self.pbar.update(n)

    def set_description(self, desc: str) -> None:
        """Update progress bar description.

        Args:
            desc: New description
        """
        self.pbar.set_description(desc)

    def set_postfix(self, **kwargs) -> None:
        """Set additional info in progress bar.

        Args:
            **kwargs: Key-value pairs to display
        """
        self.pbar.set_postfix(**kwargs)

    def close(self) -> None:
        """Close the progress bar."""
        self.pbar.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_progress_iterator(
    iterable,
    desc: str = "Processing",
    total: int | None = None,
    unit: str = "it",
):
    """Create progress bar iterator for any iterable.

    Args:
        iterable: Any iterable object
        desc: Description for progress bar
        total: Total number of items (if known)
        unit: Unit name for progress

    Returns:
        Iterator with progress tracking

    Example:
        >>> data_frames = []
        >>> for symbol in create_progress_iterator(symbols, desc="Loading data"):
        ...     df = load_data(symbol)
        ...     data_frames.append(df)
    """
    return tqdm(iterable, desc=desc, total=total, unit=unit)
