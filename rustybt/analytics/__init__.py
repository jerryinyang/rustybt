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
Analytics and visualization tools for Jupyter notebook integration.

This module provides:
- Interactive visualization functions using Plotly
- DataFrame export utilities for backtest results
- Notebook-friendly repr methods for strategy objects
- Async execution support for notebooks
- Progress bars for long-running operations
"""

from rustybt.analytics.visualization import (
    plot_equity_curve,
    plot_drawdown,
    plot_returns_distribution,
    plot_rolling_metrics,
)
from rustybt.analytics.notebook import (
    async_backtest,
    setup_notebook,
)

__all__ = [
    "plot_equity_curve",
    "plot_drawdown",
    "plot_returns_distribution",
    "plot_rolling_metrics",
    "async_backtest",
    "setup_notebook",
]
