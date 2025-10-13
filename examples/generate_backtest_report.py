#!/usr/bin/env python
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
Example: Generate Professional Backtest Reports

This example demonstrates how to generate professional PDF and HTML reports
from backtest results using the ReportGenerator class.

Features demonstrated:
- Basic report generation (HTML and PDF)
- Custom report configuration
- Selective sections (including/excluding charts)
- Custom branding (title, subtitle)
- Custom charts via callbacks

Usage:
    python examples/generate_backtest_report.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rustybt.analytics.reports import ReportConfig, ReportGenerator


def create_sample_backtest_data():
    """Create sample backtest results for demonstration.

    Returns:
        pandas.DataFrame: Sample backtest results with portfolio values and returns
    """
    print("📊 Creating sample backtest data...")

    # Generate 1 year of daily data
    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq="D")
    np.random.seed(42)

    # Simulate realistic returns with drift and volatility
    daily_return_mean = 0.0008  # ~20% annual return
    daily_return_std = 0.015  # ~24% annual volatility

    returns = np.random.normal(daily_return_mean, daily_return_std, len(dates))

    # Add some market events (larger moves)
    crash_days = np.random.choice(len(dates), size=5, replace=False)
    returns[crash_days] -= 0.05  # -5% crash days

    rally_days = np.random.choice(len(dates), size=10, replace=False)
    returns[rally_days] += 0.03  # +3% rally days

    # Calculate portfolio values
    starting_capital = 100000
    portfolio_values = starting_capital * np.exp(np.cumsum(returns))

    # Create DataFrame
    df = pd.DataFrame(
        {
            "portfolio_value": portfolio_values,
            "returns": returns,
            "ending_value": portfolio_values,
        },
        index=dates,
    )

    print(f"✅ Generated {len(df)} days of backtest data")
    print(f"   Starting Capital: ${starting_capital:,.0f}")
    print(f"   Ending Value: ${portfolio_values[-1]:,.0f}")
    print(f"   Total Return: {(portfolio_values[-1] / starting_capital - 1) * 100:.2f}%")

    return df


def example_basic_report():
    """Example 1: Generate basic HTML and PDF reports with default settings."""
    print("\n" + "=" * 70)
    print("Example 1: Basic Report Generation")
    print("=" * 70)

    # Create sample data
    backtest_data = create_sample_backtest_data()

    # Create report generator with default config
    generator = ReportGenerator(backtest_data)

    # Generate HTML report
    html_path = Path("backtest_report.html")
    print(f"\n📝 Generating HTML report: {html_path}")
    generator.generate_report(html_path, format="html")
    print(f"✅ HTML report created: {html_path.absolute()}")

    # Generate PDF report
    pdf_path = Path("backtest_report.pdf")
    print(f"\n📄 Generating PDF report: {pdf_path}")
    generator.generate_report(pdf_path, format="pdf")
    print(f"✅ PDF report created: {pdf_path.absolute()}")


def example_custom_report():
    """Example 2: Generate report with custom configuration."""
    print("\n" + "=" * 70)
    print("Example 2: Custom Report Configuration")
    print("=" * 70)

    # Create sample data
    backtest_data = create_sample_backtest_data()

    # Create custom report config
    config = ReportConfig(
        title="My Trading Strategy Report",
        subtitle="Momentum-Based Long Strategy",
        include_equity_curve=True,
        include_drawdown=True,
        include_returns_distribution=True,
        include_metrics_table=True,
        include_trade_statistics=True,
        include_position_distribution=False,  # Disable position distribution
        dpi=300,  # High resolution for print
        figsize=(12, 7),  # Larger charts
    )

    # Create generator with custom config
    generator = ReportGenerator(backtest_data, config)

    # Generate reports
    html_path = Path("custom_report.html")
    pdf_path = Path("custom_report.pdf")

    print(f"\n📝 Generating custom HTML report: {html_path}")
    generator.generate_report(html_path, format="html")
    print(f"✅ Custom HTML report created: {html_path.absolute()}")

    print(f"\n📄 Generating custom PDF report: {pdf_path}")
    generator.generate_report(pdf_path, format="pdf")
    print(f"✅ Custom PDF report created: {pdf_path.absolute()}")


def example_minimal_report():
    """Example 3: Generate minimal report with only key charts."""
    print("\n" + "=" * 70)
    print("Example 3: Minimal Report (Key Charts Only)")
    print("=" * 70)

    # Create sample data
    backtest_data = create_sample_backtest_data()

    # Create minimal config - only equity curve and metrics
    config = ReportConfig(
        title="Executive Summary Report",
        subtitle="Key Performance Indicators",
        include_equity_curve=True,
        include_drawdown=False,
        include_returns_distribution=False,
        include_metrics_table=True,
        include_trade_statistics=False,
        include_position_distribution=False,
    )

    generator = ReportGenerator(backtest_data, config)

    html_path = Path("minimal_report.html")
    print(f"\n📝 Generating minimal report: {html_path}")
    generator.generate_report(html_path, format="html")
    print(f"✅ Minimal report created: {html_path.absolute()}")


def example_custom_charts():
    """Example 4: Add custom charts to report."""
    print("\n" + "=" * 70)
    print("Example 4: Report with Custom Charts")
    print("=" * 70)

    # Create sample data
    backtest_data = create_sample_backtest_data()

    # Define custom chart functions
    def rolling_sharpe_chart(data):
        """Custom chart: Rolling 30-day Sharpe ratio."""
        import base64
        from io import BytesIO

        fig, ax = plt.subplots(figsize=(10, 6))

        returns = data["returns"]
        window = 30

        # Calculate rolling Sharpe
        rolling_mean = returns.rolling(window=window).mean() * 252
        rolling_std = returns.rolling(window=window).std() * np.sqrt(252)
        rolling_sharpe = rolling_mean / rolling_std

        ax.plot(data.index, rolling_sharpe, linewidth=2, color="#1976d2")
        ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
        ax.set_title("Rolling 30-Day Sharpe Ratio", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date")
        ax.set_ylabel("Sharpe Ratio")
        ax.grid(True, alpha=0.3)

        # Save as base64
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)

        return f"data:image/png;base64,{img_base64}"

    def monthly_returns_heatmap(data):
        """Custom chart: Monthly returns heatmap."""
        import base64
        from io import BytesIO

        fig, ax = plt.subplots(figsize=(12, 6))

        # Calculate monthly returns
        monthly_returns = data["returns"].resample("M").apply(lambda x: (1 + x).prod() - 1)

        # Create simple bar chart (heatmap would need more complex setup)
        monthly_returns_pct = monthly_returns * 100
        colors = ["#00c853" if x > 0 else "#d32f2f" for x in monthly_returns_pct]

        ax.bar(monthly_returns.index, monthly_returns_pct, color=colors, alpha=0.7)
        ax.set_title("Monthly Returns", fontsize=14, fontweight="bold")
        ax.set_xlabel("Month")
        ax.set_ylabel("Return (%)")
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax.grid(True, alpha=0.3, axis="y")
        plt.xticks(rotation=45, ha="right")

        # Save as base64
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)

        return f"data:image/png;base64,{img_base64}"

    # Create config with custom charts
    config = ReportConfig(
        title="Advanced Strategy Report",
        subtitle="With Custom Analytics",
        custom_charts=[rolling_sharpe_chart, monthly_returns_heatmap],
    )

    generator = ReportGenerator(backtest_data, config)

    html_path = Path("custom_charts_report.html")
    print(f"\n📝 Generating report with custom charts: {html_path}")
    generator.generate_report(html_path, format="html")
    print(f"✅ Report with custom charts created: {html_path.absolute()}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("🚀 RustyBT Report Generation Examples")
    print("=" * 70)

    try:
        # Run examples
        example_basic_report()
        example_custom_report()
        example_minimal_report()
        example_custom_charts()

        print("\n" + "=" * 70)
        print("✨ All examples completed successfully!")
        print("=" * 70)
        print("\nGenerated files:")
        for file in [
            "backtest_report.html",
            "backtest_report.pdf",
            "custom_report.html",
            "custom_report.pdf",
            "minimal_report.html",
            "custom_charts_report.html",
        ]:
            if Path(file).exists():
                print(f"  ✅ {file}")

        print("\n💡 Tips:")
        print("  - Open .html files in your browser to view interactive reports")
        print("  - Open .pdf files in a PDF viewer for print-ready reports")
        print("  - Customize ReportConfig for your specific needs")
        print("  - Add custom charts by defining chart generation functions")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
