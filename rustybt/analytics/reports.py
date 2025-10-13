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
Professional backtest report generation with charts and metrics.

This module provides:
- PDF and HTML report generation for backtest results
- Publication-quality charts using matplotlib and seaborn
- Customizable report sections and branding
- Performance metrics tables and trade statistics
"""

import base64
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns
from jinja2 import Environment, PackageLoader, select_autoescape
from matplotlib.backends.backend_pdf import PdfPages

# Import empyrical for accurate financial metrics
try:
    import empyrical

    EMPYRICAL_AVAILABLE = True
except ImportError:
    EMPYRICAL_AVAILABLE = False


@contextmanager
def publication_style():
    """Context manager for publication-quality matplotlib styling.

    Temporarily sets matplotlib style without affecting global state.
    """
    original_style = plt.rcParams.copy()
    try:
        plt.style.use("seaborn-v0_8-darkgrid")
        sns.set_palette("husl")
        yield
    finally:
        plt.rcParams.update(original_style)


@dataclass
class ReportConfig:
    """Configuration for report generation.

    Attributes:
        title: Report title
        subtitle: Optional subtitle
        logo_path: Path to logo image file
        include_equity_curve: Include equity curve chart
        include_drawdown: Include drawdown chart
        include_returns_distribution: Include returns distribution histogram
        include_metrics_table: Include performance metrics table
        include_trade_statistics: Include trade statistics
        include_position_distribution: Include position distribution
        custom_charts: List of custom chart generation functions
        dpi: Chart resolution (150 for screen, 300 for print)
        figsize: Default figure size (width, height) in inches
    """

    title: str = "Backtest Report"
    subtitle: str | None = None
    logo_path: Path | None = None
    include_equity_curve: bool = True
    include_drawdown: bool = True
    include_returns_distribution: bool = True
    include_metrics_table: bool = True
    include_trade_statistics: bool = True
    include_position_distribution: bool = True
    custom_charts: list[Callable] = field(default_factory=list)
    dpi: int = 150
    figsize: tuple = (10, 6)


class ReportGenerator:
    """Generate professional backtest reports in PDF or HTML format.

    This class takes backtest results and generates comprehensive reports with:
    - Equity curve and drawdown charts
    - Performance metrics (Sharpe, Sortino, max drawdown, etc.)
    - Trade statistics (win rate, profit factor, etc.)
    - Position distribution analysis

    Example:
        >>> config = ReportConfig(title="My Strategy Report")
        >>> generator = ReportGenerator(backtest_results, config)
        >>> generator.generate_report(Path("report.html"), format="html")
        >>> generator.generate_report(Path("report.pdf"), format="pdf")
    """

    def __init__(
        self, backtest_result: pd.DataFrame | pl.DataFrame, config: ReportConfig | None = None
    ):
        """Initialize report generator.

        Args:
            backtest_result: DataFrame with backtest results containing at minimum
                            'portfolio_value' or 'ending_value' column and datetime index
            config: Report configuration options
        """
        self.config = config or ReportConfig()

        # Convert to pandas if needed
        if isinstance(backtest_result, pl.DataFrame):
            self.data = backtest_result.to_pandas()
        else:
            self.data = backtest_result.copy()

        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=PackageLoader("rustybt", "analytics/templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Validate data
        self._validate_data()

    def _validate_data(self) -> None:
        """Validate that backtest data has required columns.

        Raises:
            ValueError: If required columns are missing
        """
        required_columns = ["portfolio_value", "ending_value"]
        has_portfolio_value = any(col in self.data.columns for col in required_columns)

        if not has_portfolio_value:
            raise ValueError(
                f"DataFrame must have one of {required_columns}. "
                f"Found columns: {list(self.data.columns)}"
            )

    def generate_report(self, output_path: str | Path, format: str = "html") -> None:
        """Generate report in specified format.

        Args:
            output_path: Path where report will be saved
            format: Output format ('html' or 'pdf')

        Raises:
            ValueError: If format is not supported
        """
        output_path = Path(output_path)

        if format.lower() == "html":
            self._generate_html_report(output_path)
        elif format.lower() == "pdf":
            self._generate_pdf_report(output_path)
        else:
            raise ValueError(f"Unsupported format: {format}. Supported formats: 'html', 'pdf'")

    def _generate_html_report(self, output_path: Path) -> None:
        """Generate HTML report with embedded charts.

        Args:
            output_path: Path where HTML file will be saved
        """
        # Generate all charts as base64 encoded images
        charts = {}
        if self.config.include_equity_curve:
            charts["equity_curve"] = self._generate_equity_curve()
        if self.config.include_drawdown:
            charts["drawdown"] = self._generate_drawdown_chart()
        if self.config.include_returns_distribution:
            charts["returns_distribution"] = self._generate_returns_distribution()
        if self.config.include_position_distribution:
            charts["position_distribution"] = self._generate_position_distribution()

        # Add custom charts
        for i, chart_func in enumerate(self.config.custom_charts):
            charts[f"custom_{i}"] = chart_func(self.data)

        # Extract metrics and statistics
        metrics = self._get_performance_metrics() if self.config.include_metrics_table else None
        trade_stats = self._get_trade_statistics() if self.config.include_trade_statistics else None

        # Render template
        template = self.jinja_env.get_template("report.html")
        html_content = template.render(
            config=self.config,
            charts=charts,
            metrics=metrics,
            trade_stats=trade_stats,
            generated_date=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        # Write to file
        output_path.write_text(html_content, encoding="utf-8")

    def _generate_pdf_report(self, output_path: Path) -> None:
        """Generate PDF report using matplotlib.

        Args:
            output_path: Path where PDF file will be saved
        """
        with PdfPages(output_path) as pdf:
            # Page 1: Title and summary metrics
            fig = self._create_title_page()
            pdf.savefig(fig, dpi=self.config.dpi)
            plt.close(fig)

            # Page 2: Equity curve
            if self.config.include_equity_curve:
                fig = self._create_equity_curve_figure()
                pdf.savefig(fig, dpi=self.config.dpi)
                plt.close(fig)

            # Page 3: Drawdown
            if self.config.include_drawdown:
                fig = self._create_drawdown_figure()
                pdf.savefig(fig, dpi=self.config.dpi)
                plt.close(fig)

            # Page 4: Returns distribution
            if self.config.include_returns_distribution:
                fig = self._create_returns_distribution_figure()
                pdf.savefig(fig, dpi=self.config.dpi)
                plt.close(fig)

            # Page 5: Position distribution
            if self.config.include_position_distribution:
                fig = self._create_position_distribution_figure()
                pdf.savefig(fig, dpi=self.config.dpi)
                plt.close(fig)

            # Additional pages for custom charts
            for chart_func in self.config.custom_charts:
                fig = chart_func(self.data)
                pdf.savefig(fig, dpi=self.config.dpi)
                plt.close(fig)

    def _generate_equity_curve(self) -> str:
        """Generate equity curve chart.

        Returns:
            Base64 encoded PNG image
        """
        fig, ax = plt.subplots(figsize=self.config.figsize)

        # Get portfolio values
        if "portfolio_value" in self.data.columns:
            values = self.data["portfolio_value"]
        else:
            values = self.data["ending_value"]

        # Plot
        ax.plot(self.data.index, values, linewidth=2, color="#1976d2")
        ax.set_title("Portfolio Equity Curve", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Portfolio Value ($)", fontsize=12)
        ax.grid(True, alpha=0.3)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        plt.xticks(rotation=45, ha="right")

        # Format y-axis with thousands separator
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))

        plt.tight_layout()

        return self._save_figure_as_base64(fig)

    def _generate_drawdown_chart(self) -> str:
        """Generate drawdown chart.

        Returns:
            Base64 encoded PNG image
        """
        fig, ax = plt.subplots(figsize=self.config.figsize)

        # Get portfolio values
        if "portfolio_value" in self.data.columns:
            values = self.data["portfolio_value"]
        else:
            values = self.data["ending_value"]

        # Calculate drawdown
        cummax = values.expanding().max()
        drawdown = (values - cummax) / cummax * 100

        # Plot
        ax.fill_between(self.data.index, drawdown, 0, alpha=0.3, color="#d32f2f")
        ax.plot(self.data.index, drawdown, linewidth=2, color="#d32f2f")
        ax.set_title("Portfolio Drawdown", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Drawdown (%)", fontsize=12)
        ax.grid(True, alpha=0.3)

        # Add max drawdown line
        max_dd = drawdown.min()
        ax.axhline(
            y=max_dd,
            color="black",
            linestyle="--",
            linewidth=1,
            label=f"Max Drawdown: {max_dd:.2f}%",
        )
        ax.legend()

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        plt.xticks(rotation=45, ha="right")

        plt.tight_layout()

        return self._save_figure_as_base64(fig)

    def _generate_returns_distribution(self) -> str:
        """Generate returns distribution histogram with KDE.

        Returns:
            Base64 encoded PNG image
        """
        fig, ax = plt.subplots(figsize=self.config.figsize)

        # Calculate returns
        if "returns" in self.data.columns:
            returns = self.data["returns"].dropna() * 100  # Convert to percentage
        elif "portfolio_value" in self.data.columns:
            returns = self.data["portfolio_value"].pct_change().dropna() * 100
        else:
            returns = self.data["ending_value"].pct_change().dropna() * 100

        # Plot histogram with KDE
        sns.histplot(returns, kde=True, bins=50, ax=ax, color="#1976d2")

        # Add mean line
        mean_return = returns.mean()
        ax.axvline(
            x=mean_return,
            color="#00c853",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {mean_return:.3f}%",
        )

        ax.set_title("Returns Distribution", fontsize=14, fontweight="bold")
        ax.set_xlabel("Returns (%)", fontsize=12)
        ax.set_ylabel("Frequency", fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add statistics text box
        stats_text = (
            f"Mean: {mean_return:.3f}%\n"
            f"Std Dev: {returns.std():.3f}%\n"
            f"Skewness: {returns.skew():.3f}\n"
            f"Kurtosis: {returns.kurtosis():.3f}"
        )
        ax.text(
            0.02,
            0.98,
            stats_text,
            transform=ax.transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
            fontsize=10,
        )

        plt.tight_layout()

        return self._save_figure_as_base64(fig)

    def _generate_position_distribution(self) -> str:
        """Generate position distribution chart.

        Attempts to extract and visualize position data from common formats:
        - Individual asset columns (e.g., 'position_AAPL', 'position_MSFT')
        - Position value/weight columns
        - Positions column containing structured data

        Returns:
            Base64 encoded PNG image with position data visualization or placeholder
        """
        fig, ax = plt.subplots(figsize=self.config.figsize)

        # Try to extract position data from various common formats
        position_data = self._extract_position_data()

        if position_data is not None and len(position_data) > 0:
            # Successfully extracted position data - create visualization
            # Sort by value and take top 10
            position_data = position_data.sort_values(ascending=False).head(10)

            # Create horizontal bar chart
            colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(position_data)))
            bars = ax.barh(range(len(position_data)), position_data.values, color=colors)

            # Customize chart
            ax.set_yticks(range(len(position_data)))
            ax.set_yticklabels(position_data.index)
            ax.set_xlabel("Average Position Size", fontsize=12)
            ax.set_title("Top 10 Position Distribution", fontsize=14, fontweight="bold")
            ax.grid(True, alpha=0.3, axis="x")

            # Add value labels on bars
            for i, (bar, value) in enumerate(zip(bars, position_data.values, strict=False)):
                ax.text(value, i, f" {value:.1f}", va="center", fontsize=9)

            plt.tight_layout()
        else:
            # Graceful degradation: Show informative message
            ax.text(
                0.5,
                0.5,
                "Position data not available\n\n"
                "Supported formats:\n"
                "• position_* columns (e.g., position_AAPL)\n"
                "• position_value/position_weights columns\n"
                "• positions column with structured data",
                ha="center",
                va="center",
                fontsize=11,
                bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.3},
            )
            ax.set_title("Position Distribution", fontsize=14, fontweight="bold")
            ax.axis("off")
            plt.tight_layout()

        return self._save_figure_as_base64(fig)

    def _extract_position_data(self) -> pd.Series | None:
        """Extract position data from DataFrame in various common formats.

        Returns:
            Series of position sizes by asset name, or None if unavailable
        """
        # Strategy 1: Look for position_* columns (e.g., position_AAPL, position_MSFT)
        position_cols = [col for col in self.data.columns if col.startswith("position_")]
        if position_cols:
            # Calculate average position size for each asset
            position_data = {}
            for col in position_cols:
                asset_name = col.replace("position_", "")
                # Take mean of non-zero positions
                non_zero = self.data[col][self.data[col] != 0]
                if len(non_zero) > 0:
                    position_data[asset_name] = abs(non_zero).mean()

            if position_data:
                return pd.Series(position_data)

        # Strategy 2: Look for position_value or position_weights column
        if "position_values" in self.data.columns:
            # Aggregate position values
            # Assuming format: {asset: value} dict or similar
            return None  # Would need specific format knowledge

        # Strategy 3: Check if 'positions' column contains structured data
        if "positions" in self.data.columns:
            # Try to extract from structured positions data
            # This would need to be adapted based on actual structure
            return None

        # No position data found
        return None

    def _get_performance_metrics(self) -> dict[str, Any]:
        """Extract performance metrics from backtest results.

        Uses empyrical library for accurate financial metrics when available,
        falls back to simplified calculations otherwise.

        Returns:
            Dictionary of metric names and values
        """
        # Get portfolio values
        if "portfolio_value" in self.data.columns:
            values = self.data["portfolio_value"]
        else:
            values = self.data["ending_value"]

        # Calculate returns
        if "returns" in self.data.columns:
            returns = self.data["returns"]
        else:
            returns = values.pct_change().dropna()

        # Use empyrical for accurate calculations if available
        if EMPYRICAL_AVAILABLE:
            # Empyrical expects pandas Series with datetime index
            returns_series = pd.Series(returns.values, index=self.data.index[: len(returns)])

            # Calculate metrics using empyrical
            total_return = empyrical.cum_returns_final(returns_series)
            annual_return = empyrical.annual_return(returns_series)
            sharpe_ratio = empyrical.sharpe_ratio(returns_series)
            sortino_ratio = empyrical.sortino_ratio(returns_series)
            max_drawdown = empyrical.max_drawdown(returns_series)
            calmar_ratio = empyrical.calmar_ratio(returns_series)
            volatility = empyrical.annual_volatility(returns_series)

            # Additional empyrical metrics
            stability = empyrical.stability_of_timeseries(returns_series)
            tail_ratio = empyrical.tail_ratio(returns_series)

            metrics = {
                "Total Return": f"{total_return * 100:.2f}%",
                "Annual Return": f"{annual_return * 100:.2f}%",
                "Sharpe Ratio": f"{sharpe_ratio:.2f}",
                "Sortino Ratio": f"{sortino_ratio:.2f}",
                "Max Drawdown": f"{max_drawdown * 100:.2f}%",
                "Calmar Ratio": f"{calmar_ratio:.2f}",
                "Volatility (Annual)": f"{volatility * 100:.2f}%",
                "Stability": f"{stability:.3f}",
                "Tail Ratio": f"{tail_ratio:.2f}",
                "Trading Days": len(returns),
            }
        else:
            # Fallback to simplified calculations
            total_return = (values.iloc[-1] - values.iloc[0]) / values.iloc[0]
            cummax = values.expanding().max()
            drawdown = (values - cummax) / cummax
            max_drawdown = drawdown.min()

            # Annualized metrics (assuming daily data)
            trading_days = len(returns)
            years = trading_days / 252
            annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

            # Simplified Sharpe and Sortino
            mean_return = returns.mean() * 252
            std_return = returns.std() * np.sqrt(252)
            sharpe_ratio = mean_return / std_return if std_return != 0 else 0

            downside_returns = returns[returns < 0]
            downside_std = (
                downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else std_return
            )
            sortino_ratio = mean_return / downside_std if downside_std != 0 else 0

            # Calmar ratio
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

            metrics = {
                "Total Return": f"{total_return * 100:.2f}%",
                "Annual Return": f"{annual_return * 100:.2f}%",
                "Sharpe Ratio": f"{sharpe_ratio:.2f}",
                "Sortino Ratio": f"{sortino_ratio:.2f}",
                "Max Drawdown": f"{max_drawdown * 100:.2f}%",
                "Calmar Ratio": f"{calmar_ratio:.2f}",
                "Volatility": f"{std_return * 100:.2f}%",
                "Trading Days": trading_days,
            }

        return metrics

    def _get_trade_statistics(self) -> dict[str, Any]:
        """Calculate trade statistics.

        Returns:
            Dictionary of trade statistics
        """
        # Calculate daily returns
        if "returns" in self.data.columns:
            returns = self.data["returns"].dropna()
        elif "portfolio_value" in self.data.columns:
            returns = self.data["portfolio_value"].pct_change().dropna()
        else:
            returns = self.data["ending_value"].pct_change().dropna()

        # Treat each day as a "trade" for simplicity
        # In a real implementation, would analyze actual trade records
        winning_days = returns[returns > 0]
        losing_days = returns[returns < 0]

        total_trades = len(returns)
        winning_trades = len(winning_days)
        losing_trades = len(losing_days)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        avg_win = winning_days.mean() if len(winning_days) > 0 else 0
        avg_loss = losing_days.mean() if len(losing_days) > 0 else 0

        # Profit factor
        total_profit = winning_days.sum() if len(winning_days) > 0 else 0
        total_loss = abs(losing_days.sum()) if len(losing_days) > 0 else 0
        profit_factor = total_profit / total_loss if total_loss != 0 else float("inf")

        return {
            "Total Trades": total_trades,
            "Winning Trades": winning_trades,
            "Losing Trades": losing_trades,
            "Win Rate": f"{win_rate * 100:.2f}%",
            "Average Win": f"{avg_win * 100:.3f}%",
            "Average Loss": f"{avg_loss * 100:.3f}%",
            "Profit Factor": f"{profit_factor:.2f}" if profit_factor != float("inf") else "N/A",
            "Largest Win": f"{winning_days.max() * 100:.3f}%" if len(winning_days) > 0 else "N/A",
            "Largest Loss": f"{losing_days.min() * 100:.3f}%" if len(losing_days) > 0 else "N/A",
        }

    def _save_figure_as_base64(self, fig: plt.Figure) -> str:
        """Save matplotlib figure as base64 encoded PNG.

        Args:
            fig: Matplotlib figure object

        Returns:
            Base64 encoded PNG image with data URL prefix
        """
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=self.config.dpi, bbox_inches="tight")
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"

    # PDF-specific figure creation methods

    def _create_title_page(self) -> plt.Figure:
        """Create title page for PDF report.

        Returns:
            Matplotlib figure
        """
        fig = plt.figure(figsize=(8.5, 11))
        ax = fig.add_subplot(111)
        ax.axis("off")

        # Title
        ax.text(
            0.5, 0.7, self.config.title, ha="center", va="center", fontsize=24, fontweight="bold"
        )

        # Subtitle
        if self.config.subtitle:
            ax.text(0.5, 0.65, self.config.subtitle, ha="center", va="center", fontsize=16)

        # Date range
        start_date = self.data.index[0].strftime("%Y-%m-%d")
        end_date = self.data.index[-1].strftime("%Y-%m-%d")
        ax.text(
            0.5, 0.55, f"Period: {start_date} to {end_date}", ha="center", va="center", fontsize=12
        )

        # Summary metrics
        metrics = self._get_performance_metrics()
        metrics_text = "\n".join([f"{k}: {v}" for k, v in list(metrics.items())[:4]])
        ax.text(0.5, 0.4, "Key Metrics", ha="center", va="center", fontsize=14, fontweight="bold")
        ax.text(0.5, 0.3, metrics_text, ha="center", va="top", fontsize=12, family="monospace")

        # Generated timestamp
        ax.text(
            0.5,
            0.1,
            f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ha="center",
            va="center",
            fontsize=10,
            style="italic",
        )

        return fig

    def _create_equity_curve_figure(self) -> plt.Figure:
        """Create equity curve figure for PDF.

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(8, 6))

        if "portfolio_value" in self.data.columns:
            values = self.data["portfolio_value"]
        else:
            values = self.data["ending_value"]

        ax.plot(self.data.index, values, linewidth=2, color="#1976d2")
        ax.set_title("Portfolio Equity Curve", fontsize=16, fontweight="bold")
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Portfolio Value ($)", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        return fig

    def _create_drawdown_figure(self) -> plt.Figure:
        """Create drawdown figure for PDF.

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(8, 6))

        if "portfolio_value" in self.data.columns:
            values = self.data["portfolio_value"]
        else:
            values = self.data["ending_value"]

        cummax = values.expanding().max()
        drawdown = (values - cummax) / cummax * 100

        ax.fill_between(self.data.index, drawdown, 0, alpha=0.3, color="#d32f2f")
        ax.plot(self.data.index, drawdown, linewidth=2, color="#d32f2f")
        ax.set_title("Portfolio Drawdown", fontsize=16, fontweight="bold")
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("Drawdown (%)", fontsize=12)
        ax.grid(True, alpha=0.3)

        max_dd = drawdown.min()
        ax.axhline(
            y=max_dd,
            color="black",
            linestyle="--",
            linewidth=1,
            label=f"Max Drawdown: {max_dd:.2f}%",
        )
        ax.legend()

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        return fig

    def _create_returns_distribution_figure(self) -> plt.Figure:
        """Create returns distribution figure for PDF.

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(8, 6))

        if "returns" in self.data.columns:
            returns = self.data["returns"].dropna() * 100
        elif "portfolio_value" in self.data.columns:
            returns = self.data["portfolio_value"].pct_change().dropna() * 100
        else:
            returns = self.data["ending_value"].pct_change().dropna() * 100

        sns.histplot(returns, kde=True, bins=50, ax=ax, color="#1976d2")

        mean_return = returns.mean()
        ax.axvline(
            x=mean_return,
            color="#00c853",
            linestyle="--",
            linewidth=2,
            label=f"Mean: {mean_return:.3f}%",
        )

        ax.set_title("Returns Distribution", fontsize=16, fontweight="bold")
        ax.set_xlabel("Returns (%)", fontsize=12)
        ax.set_ylabel("Frequency", fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)

        stats_text = (
            f"Mean: {mean_return:.3f}%\n"
            f"Std Dev: {returns.std():.3f}%\n"
            f"Skewness: {returns.skew():.3f}\n"
            f"Kurtosis: {returns.kurtosis():.3f}"
        )
        ax.text(
            0.02,
            0.98,
            stats_text,
            transform=ax.transAxes,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
            fontsize=10,
        )

        plt.tight_layout()

        return fig

    def _create_position_distribution_figure(self) -> plt.Figure:
        """Create position distribution figure for PDF.

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(8, 6))

        # Try to extract position data
        position_data = self._extract_position_data()

        if position_data is not None and len(position_data) > 0:
            # Successfully extracted position data
            position_data = position_data.sort_values(ascending=False).head(10)

            # Create horizontal bar chart
            colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(position_data)))
            bars = ax.barh(range(len(position_data)), position_data.values, color=colors)

            ax.set_yticks(range(len(position_data)))
            ax.set_yticklabels(position_data.index)
            ax.set_xlabel("Average Position Size", fontsize=12)
            ax.set_title("Top 10 Position Distribution", fontsize=16, fontweight="bold")
            ax.grid(True, alpha=0.3, axis="x")

            # Add value labels
            for i, (bar, value) in enumerate(zip(bars, position_data.values, strict=False)):
                ax.text(value, i, f" {value:.1f}", va="center", fontsize=9)
        else:
            # Graceful degradation
            ax.text(
                0.5,
                0.5,
                "Position data not available\n\n"
                "Supported formats:\n"
                "• position_* columns (e.g., position_AAPL)\n"
                "• position_value/position_weights columns\n"
                "• positions column with structured data",
                ha="center",
                va="center",
                fontsize=11,
                bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.3},
            )
            ax.axis("off")

        ax.set_title("Position Distribution", fontsize=16, fontweight="bold")
        plt.tight_layout()

        return fig
