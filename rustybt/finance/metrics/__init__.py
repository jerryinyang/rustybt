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
import empyrical

from rustybt.utils.deprecate import deprecated

from .advanced import (
    CalmarRatioMetric,
    CVaRMetric,
    TradeStatisticsMetric,
    VaRMetric,
    calmar_ratio,
    conditional_value_at_risk,
    profit_factor,
    value_at_risk,
    win_rate,
)
from .attribution import (
    calculate_alpha_beta,
    calculate_position_attribution,
    calculate_sector_attribution,
    calculate_time_period_attribution,
)
from .core import (
    load,
    metrics_sets,
    register,
    unregister,
)

# Decimal precision metrics (Story 2.4)
from .decimal_metrics import (
    InsufficientDataError,
    InvalidMetricError,
    MetricsError,
    calculate_calmar_ratio,
    calculate_cvar,
    calculate_excess_return,
    calculate_information_ratio,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_tracking_error,
    calculate_var,
    calculate_win_rate,
)
from .decimal_tracker import DecimalMetricsTracker
from .empyrical_adapter import (
    EmpyricalAdapter,
    compare_metrics,
    from_float_value,
    to_float_series,
    validate_decimal_against_empyrical,
)
from .formatting import (
    create_metrics_summary_table,
    format_basis_points,
    format_currency,
    format_metrics_html,
    format_percentage,
    format_ratio,
    metrics_to_csv_row,
    metrics_to_json,
)
from .metric import (
    PNL,
    AlphaBeta,
    BenchmarkReturnsAndVolatility,
    CashFlow,
    DailyLedgerField,
    MaxLeverage,
    NumTradingDays,
    Orders,
    PeriodLabel,
    Returns,
    ReturnsStatistic,
    SimpleLedgerField,
    StartOfPeriodLedgerField,
    Transactions,
    _ClassicRiskMetrics,
    _ConstantCumulativeRiskMetric,
)
from .tracker import MetricsTracker

__all__ = [
    "MetricsTracker",
    "unregister",
    "metrics_sets",
    "load",
    # Decimal metrics
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_max_drawdown",
    "calculate_calmar_ratio",
    "calculate_var",
    "calculate_cvar",
    "calculate_win_rate",
    "calculate_profit_factor",
    "calculate_excess_return",
    "calculate_information_ratio",
    "calculate_tracking_error",
    # Attribution
    "calculate_position_attribution",
    "calculate_sector_attribution",
    "calculate_alpha_beta",
    "calculate_time_period_attribution",
    # Tracker
    "DecimalMetricsTracker",
    # Formatting
    "format_percentage",
    "format_ratio",
    "format_currency",
    "format_basis_points",
    "create_metrics_summary_table",
    "metrics_to_json",
    "metrics_to_csv_row",
    "format_metrics_html",
    # Empyrical adapter
    "EmpyricalAdapter",
    "to_float_series",
    "from_float_value",
    "compare_metrics",
    "validate_decimal_against_empyrical",
    # Exceptions
    "MetricsError",
    "InsufficientDataError",
    "InvalidMetricError",
]


register("none", set)


@register("default")
def default_metrics():
    return {
        Returns(),
        ReturnsStatistic(empyrical.annual_volatility, "algo_volatility"),
        BenchmarkReturnsAndVolatility(),
        PNL(),
        CashFlow(),
        Orders(),
        Transactions(),
        SimpleLedgerField("positions"),
        StartOfPeriodLedgerField(
            "portfolio.positions_exposure",
            "starting_exposure",
        ),
        DailyLedgerField(
            "portfolio.positions_exposure",
            "ending_exposure",
        ),
        StartOfPeriodLedgerField("portfolio.positions_value", "starting_value"),
        DailyLedgerField("portfolio.positions_value", "ending_value"),
        StartOfPeriodLedgerField("portfolio.cash", "starting_cash"),
        DailyLedgerField("portfolio.cash", "ending_cash"),
        DailyLedgerField("portfolio.portfolio_value"),
        DailyLedgerField("position_tracker.stats.longs_count"),
        DailyLedgerField("position_tracker.stats.shorts_count"),
        DailyLedgerField("position_tracker.stats.long_value"),
        DailyLedgerField("position_tracker.stats.short_value"),
        DailyLedgerField("position_tracker.stats.long_exposure"),
        DailyLedgerField("position_tracker.stats.short_exposure"),
        DailyLedgerField("account.gross_leverage"),
        DailyLedgerField("account.net_leverage"),
        AlphaBeta(),
        ReturnsStatistic(empyrical.sharpe_ratio, "sharpe"),
        ReturnsStatistic(empyrical.sortino_ratio, "sortino"),
        ReturnsStatistic(empyrical.max_drawdown),
        MaxLeverage(),
        # Advanced metrics (Story 1.6)
        CalmarRatioMetric(),
        VaRMetric(),
        CVaRMetric(),
        TradeStatisticsMetric(),
        # Please kill these!
        _ConstantCumulativeRiskMetric("excess_return", 0.0),
        _ConstantCumulativeRiskMetric("treasury_period_return", 0.0),
        NumTradingDays(),
        PeriodLabel(),
    }


@register("classic")
@deprecated(
    "The original risk packet has been deprecated and will be removed in a "
    'future release. Please use "default" metrics instead.'
)
def classic_metrics():
    metrics = default_metrics()
    metrics.add(_ClassicRiskMetrics())
    return metrics
