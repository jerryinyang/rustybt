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
- Report generation with PDF and HTML output
- DataFrame export utilities for backtest results
- Notebook-friendly repr methods for strategy objects
- Async execution support for notebooks
- Progress bars for long-running operations
"""

from rustybt.analytics.attribution import (
    AttributionError,
    InsufficientDataError,
    PerformanceAttribution,
)
from rustybt.analytics.notebook import (
    async_backtest,
    create_progress_iterator,
    setup_notebook,
)
from rustybt.analytics.reports import (
    ReportConfig,
    ReportGenerator,
)
from rustybt.analytics.risk import (
    InsufficientDataError as RiskInsufficientDataError,
)
from rustybt.analytics.risk import (
    RiskAnalytics,
    RiskError,
)
from rustybt.analytics.trade_analysis import (
    InsufficientTradeDataError,
    Trade,
    TradeAnalysisError,
    TradeAnalyzer,
)
from rustybt.analytics.visualization import (
    plot_drawdown,
    plot_equity_curve,
    plot_returns_distribution,
    plot_rolling_metrics,
)

__all__ = [
    "AttributionError",
    "InsufficientDataError",
    "InsufficientTradeDataError",
    "PerformanceAttribution",
    "ReportConfig",
    "ReportGenerator",
    "RiskAnalytics",
    "RiskError",
    "RiskInsufficientDataError",
    "Trade",
    "TradeAnalysisError",
    "TradeAnalyzer",
    "async_backtest",
    "create_progress_iterator",
    "plot_drawdown",
    "plot_equity_curve",
    "plot_returns_distribution",
    "plot_rolling_metrics",
    "setup_notebook",
]
