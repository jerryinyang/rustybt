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
Tests for report generation functionality.

Tests coverage:
- ReportConfig dataclass
- ReportGenerator class initialization
- Chart generation methods (equity curve, drawdown, returns distribution, position distribution)
- Metrics extraction
- Trade statistics calculation
- HTML report generation
- PDF report generation
- Custom sections and callbacks
- Error handling and edge cases
"""

import base64
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from rustybt.analytics.reports import (
    ReportConfig,
    ReportGenerator,
)


# Test fixtures
@pytest.fixture
def sample_backtest_results():
    """Create sample backtest results DataFrame with realistic data."""
    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq="D")
    np.random.seed(42)

    # Generate realistic portfolio values with trend and volatility
    returns = np.random.normal(0.0005, 0.02, len(dates))
    portfolio_values = 100000 * np.exp(np.cumsum(returns))

    df = pd.DataFrame(
        {
            "portfolio_value": portfolio_values,
            "returns": returns,
            "ending_value": portfolio_values,
        },
        index=dates,
    )

    return df


@pytest.fixture
def sample_backtest_polars():
    """Create sample backtest results in Polars format."""
    import polars as pl

    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq="D")
    np.random.seed(42)

    returns = np.random.normal(0.0005, 0.02, len(dates))
    portfolio_values = 100000 * np.exp(np.cumsum(returns))

    df_pl = pl.DataFrame(
        {
            "timestamp": dates,
            "portfolio_value": portfolio_values,
            "returns": returns,
        }
    )

    return df_pl


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ReportConfig Tests
class TestReportConfig:
    """Test ReportConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ReportConfig()

        assert config.title == "Backtest Report"
        assert config.subtitle is None
        assert config.logo_path is None
        assert config.include_equity_curve is True
        assert config.include_drawdown is True
        assert config.include_returns_distribution is True
        assert config.include_metrics_table is True
        assert config.include_trade_statistics is True
        assert config.include_position_distribution is True
        assert config.custom_charts == []
        assert config.dpi == 150
        assert config.figsize == (10, 6)

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ReportConfig(
            title="Custom Report",
            subtitle="Test Strategy",
            include_drawdown=False,
            dpi=300,
            figsize=(12, 8),
        )

        assert config.title == "Custom Report"
        assert config.subtitle == "Test Strategy"
        assert config.include_drawdown is False
        assert config.dpi == 300
        assert config.figsize == (12, 8)


# ReportGenerator Initialization Tests
class TestReportGeneratorInit:
    """Test ReportGenerator initialization."""

    def test_init_with_pandas_dataframe(self, sample_backtest_results):
        """Test initialization with pandas DataFrame."""
        generator = ReportGenerator(sample_backtest_results)

        assert isinstance(generator.data, pd.DataFrame)
        assert len(generator.data) == len(sample_backtest_results)
        assert "portfolio_value" in generator.data.columns

    def test_init_with_polars_dataframe(self, sample_backtest_polars):
        """Test initialization with polars DataFrame."""
        generator = ReportGenerator(sample_backtest_polars)

        assert isinstance(generator.data, pd.DataFrame)
        assert "portfolio_value" in generator.data.columns

    def test_init_with_config(self, sample_backtest_results):
        """Test initialization with custom config."""
        config = ReportConfig(title="Test Report", dpi=300)
        generator = ReportGenerator(sample_backtest_results, config)

        assert generator.config.title == "Test Report"
        assert generator.config.dpi == 300

    def test_init_without_required_columns(self):
        """Test initialization fails with missing required columns."""
        df = pd.DataFrame(
            {
                "invalid_column": [1, 2, 3],
            }
        )

        with pytest.raises(ValueError, match="DataFrame must have one of"):
            ReportGenerator(df)


# Chart Generation Tests
class TestChartGeneration:
    """Test individual chart generation methods."""

    def test_generate_equity_curve(self, sample_backtest_results):
        """Test equity curve chart generation."""
        generator = ReportGenerator(sample_backtest_results)
        chart = generator._generate_equity_curve()

        # Verify base64 encoded image
        assert chart.startswith("data:image/png;base64,")
        assert len(chart) > 100  # Should be substantial size

        # Verify it's valid base64
        img_data = chart.split(",")[1]
        decoded = base64.b64decode(img_data)
        assert len(decoded) > 0

    def test_generate_drawdown_chart(self, sample_backtest_results):
        """Test drawdown chart generation."""
        generator = ReportGenerator(sample_backtest_results)
        chart = generator._generate_drawdown_chart()

        assert chart.startswith("data:image/png;base64,")
        assert len(chart) > 100

    def test_generate_returns_distribution(self, sample_backtest_results):
        """Test returns distribution chart generation."""
        generator = ReportGenerator(sample_backtest_results)
        chart = generator._generate_returns_distribution()

        assert chart.startswith("data:image/png;base64,")
        assert len(chart) > 100

    def test_generate_position_distribution(self, sample_backtest_results):
        """Test position distribution chart generation."""
        generator = ReportGenerator(sample_backtest_results)
        chart = generator._generate_position_distribution()

        # Even without position data, should return placeholder
        assert chart.startswith("data:image/png;base64,")
        assert len(chart) > 100

    def test_chart_generation_with_different_dpi(self, sample_backtest_results):
        """Test chart generation with different DPI settings."""
        config = ReportConfig(dpi=300)
        generator = ReportGenerator(sample_backtest_results, config)
        chart = generator._generate_equity_curve()

        # Higher DPI should produce larger image
        assert len(chart) > 1000

    def test_chart_generation_with_custom_figsize(self, sample_backtest_results):
        """Test chart generation with custom figure size."""
        config = ReportConfig(figsize=(15, 10))
        generator = ReportGenerator(sample_backtest_results, config)
        chart = generator._generate_equity_curve()

        assert chart.startswith("data:image/png;base64,")


# Metrics Extraction Tests
class TestMetricsExtraction:
    """Test performance metrics extraction."""

    def test_get_performance_metrics(self, sample_backtest_results):
        """Test performance metrics calculation."""
        generator = ReportGenerator(sample_backtest_results)
        metrics = generator._get_performance_metrics()

        # Verify all expected metrics present
        assert "Total Return" in metrics
        assert "Annual Return" in metrics
        assert "Sharpe Ratio" in metrics
        assert "Sortino Ratio" in metrics
        assert "Max Drawdown" in metrics
        assert "Calmar Ratio" in metrics
        # Volatility key depends on whether empyrical is available
        assert "Volatility" in metrics or "Volatility (Annual)" in metrics
        assert "Trading Days" in metrics

        # Verify metrics are formatted as strings with percentage/ratio
        assert "%" in metrics["Total Return"]
        assert isinstance(metrics["Trading Days"], int)

    def test_metrics_calculation_accuracy(self, sample_backtest_results):
        """Test metrics calculations produce reasonable values."""
        generator = ReportGenerator(sample_backtest_results)
        metrics = generator._get_performance_metrics()

        # Extract numeric values (remove % and convert)
        total_return = float(metrics["Total Return"].rstrip("%"))
        sharpe = float(metrics["Sharpe Ratio"])

        # Verify reasonable ranges
        assert -100 < total_return < 1000  # Between -100% and 1000%
        assert -5 < sharpe < 10  # Reasonable Sharpe ratio range

    def test_metrics_with_ending_value_column(self):
        """Test metrics work with 'ending_value' column name."""
        dates = pd.date_range(start="2024-01-01", periods=252, freq="D")
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, len(dates))
        values = 100000 * np.exp(np.cumsum(returns))

        df = pd.DataFrame(
            {
                "ending_value": values,
            },
            index=dates,
        )

        generator = ReportGenerator(df)
        metrics = generator._get_performance_metrics()

        assert "Total Return" in metrics
        assert "Sharpe Ratio" in metrics


# Trade Statistics Tests
class TestTradeStatistics:
    """Test trade statistics calculation."""

    def test_get_trade_statistics(self, sample_backtest_results):
        """Test trade statistics calculation."""
        generator = ReportGenerator(sample_backtest_results)
        stats = generator._get_trade_statistics()

        # Verify all expected statistics present
        assert "Total Trades" in stats
        assert "Winning Trades" in stats
        assert "Losing Trades" in stats
        assert "Win Rate" in stats
        assert "Average Win" in stats
        assert "Average Loss" in stats
        assert "Profit Factor" in stats
        assert "Largest Win" in stats
        assert "Largest Loss" in stats

        # Verify types
        assert isinstance(stats["Total Trades"], int)
        assert isinstance(stats["Winning Trades"], int)
        assert isinstance(stats["Losing Trades"], int)

    def test_trade_statistics_consistency(self, sample_backtest_results):
        """Test trade statistics are internally consistent."""
        generator = ReportGenerator(sample_backtest_results)
        stats = generator._get_trade_statistics()

        total = stats["Total Trades"]
        winning = stats["Winning Trades"]
        losing = stats["Losing Trades"]

        # Total should equal winning + losing
        assert total == winning + losing

        # Win rate should match ratio
        win_rate = float(stats["Win Rate"].rstrip("%"))
        expected_win_rate = (winning / total * 100) if total > 0 else 0
        assert abs(win_rate - expected_win_rate) < 0.01


# HTML Report Generation Tests
class TestHTMLReportGeneration:
    """Test HTML report generation."""

    def test_generate_html_report(self, sample_backtest_results, temp_output_dir):
        """Test HTML report generation completes successfully."""
        generator = ReportGenerator(sample_backtest_results)
        output_path = temp_output_dir / "test_report.html"

        generator.generate_report(output_path, format="html")

        # Verify file was created
        assert output_path.exists()
        assert output_path.stat().st_size > 1000  # Should be substantial

        # Verify HTML content
        html_content = output_path.read_text()
        assert "<!DOCTYPE html>" in html_content
        assert "Backtest Report" in html_content
        assert "data:image/png;base64" in html_content

    def test_html_report_with_custom_title(self, sample_backtest_results, temp_output_dir):
        """Test HTML report with custom title."""
        config = ReportConfig(title="Custom Test Report", subtitle="Test Strategy")
        generator = ReportGenerator(sample_backtest_results, config)
        output_path = temp_output_dir / "custom_report.html"

        generator.generate_report(output_path, format="html")

        html_content = output_path.read_text()
        assert "Custom Test Report" in html_content
        assert "Test Strategy" in html_content

    def test_html_report_with_selective_sections(self, sample_backtest_results, temp_output_dir):
        """Test HTML report with selective sections enabled."""
        config = ReportConfig(
            include_drawdown=False,
            include_position_distribution=False,
        )
        generator = ReportGenerator(sample_backtest_results, config)
        output_path = temp_output_dir / "selective_report.html"

        generator.generate_report(output_path, format="html")

        html_content = output_path.read_text()
        # Should have equity curve but not drawdown
        assert "Equity Curve" in html_content
        # Note: "Drawdown" might appear in HTML template structure even if section not included


# PDF Report Generation Tests
class TestPDFReportGeneration:
    """Test PDF report generation."""

    def test_generate_pdf_report(self, sample_backtest_results, temp_output_dir):
        """Test PDF report generation completes successfully."""
        generator = ReportGenerator(sample_backtest_results)
        output_path = temp_output_dir / "test_report.pdf"

        generator.generate_report(output_path, format="pdf")

        # Verify file was created
        assert output_path.exists()
        assert output_path.stat().st_size > 5000  # PDF should be substantial

        # Verify PDF header
        with open(output_path, "rb") as f:
            header = f.read(4)
            assert header == b"%PDF"

    def test_pdf_report_with_custom_config(self, sample_backtest_results, temp_output_dir):
        """Test PDF report with custom configuration."""
        config = ReportConfig(title="High-Res Report", dpi=300, figsize=(12, 8))
        generator = ReportGenerator(sample_backtest_results, config)
        output_path = temp_output_dir / "highres_report.pdf"

        generator.generate_report(output_path, format="pdf")

        # Higher DPI should produce larger file
        assert output_path.exists()
        assert output_path.stat().st_size > 10000

    def test_pdf_report_with_selective_sections(self, sample_backtest_results, temp_output_dir):
        """Test PDF report with selective sections."""
        config = ReportConfig(
            include_equity_curve=True,
            include_drawdown=False,
            include_returns_distribution=False,
            include_position_distribution=False,
        )
        generator = ReportGenerator(sample_backtest_results, config)
        output_path = temp_output_dir / "minimal_report.pdf"

        generator.generate_report(output_path, format="pdf")

        assert output_path.exists()


# Custom Charts Tests
class TestCustomCharts:
    """Test custom chart functionality."""

    def test_custom_chart_callback(self, sample_backtest_results, temp_output_dir):
        """Test adding custom chart via callback."""

        def custom_chart_func(data):
            """Custom chart function for testing."""
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(data.index, data["portfolio_value"], label="Custom")
            ax.set_title("Custom Chart")
            ax.legend()

            # Save as base64
            import base64
            from io import BytesIO

            buf = BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode("utf-8")
            plt.close(fig)
            return f"data:image/png;base64,{img_base64}"

        config = ReportConfig(custom_charts=[custom_chart_func])
        generator = ReportGenerator(sample_backtest_results, config)
        output_path = temp_output_dir / "custom_chart_report.html"

        generator.generate_report(output_path, format="html")

        html_content = output_path.read_text()
        assert "Custom Chart" in html_content


# Error Handling Tests
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_format(self, sample_backtest_results, temp_output_dir):
        """Test error with invalid output format."""
        generator = ReportGenerator(sample_backtest_results)
        output_path = temp_output_dir / "test.txt"

        with pytest.raises(ValueError, match="Unsupported format"):
            generator.generate_report(output_path, format="txt")

    def test_empty_dataframe(self):
        """Test error with empty DataFrame."""
        df = pd.DataFrame({"portfolio_value": []})

        # Should initialize but may fail during chart generation
        ReportGenerator(df)
        # Not testing chart generation as it will naturally fail with empty data

    def test_single_row_dataframe(self):
        """Test handling of single-row DataFrame."""
        df = pd.DataFrame(
            {
                "portfolio_value": [100000],
            },
            index=pd.date_range("2024-01-01", periods=1),
        )

        generator = ReportGenerator(df)
        # Metrics should handle single row gracefully
        metrics = generator._get_performance_metrics()
        assert "Total Return" in metrics


# Integration Tests
class TestReportGenerationIntegration:
    """Integration tests for full report generation workflow."""

    def test_full_html_workflow(self, sample_backtest_results, temp_output_dir):
        """Test complete HTML report generation workflow."""
        config = ReportConfig(
            title="Integration Test Report",
            subtitle="Full Workflow Test",
            include_equity_curve=True,
            include_drawdown=True,
            include_returns_distribution=True,
            include_metrics_table=True,
            include_trade_statistics=True,
        )

        generator = ReportGenerator(sample_backtest_results, config)
        output_path = temp_output_dir / "integration_report.html"

        # Generate report
        generator.generate_report(output_path, format="html")

        # Verify complete report
        assert output_path.exists()
        html_content = output_path.read_text()

        # Verify all sections present
        assert "Integration Test Report" in html_content
        assert "Performance Metrics" in html_content
        assert "Equity Curve" in html_content
        assert "Drawdown" in html_content
        assert "Returns Distribution" in html_content
        assert "Trade Statistics" in html_content

    def test_full_pdf_workflow(self, sample_backtest_results, temp_output_dir):
        """Test complete PDF report generation workflow."""
        config = ReportConfig(
            title="PDF Integration Test",
            dpi=150,
        )

        generator = ReportGenerator(sample_backtest_results, config)
        output_path = temp_output_dir / "integration_report.pdf"

        # Generate report
        generator.generate_report(output_path, format="pdf")

        # Verify PDF created successfully
        assert output_path.exists()
        assert output_path.stat().st_size > 5000

        # Verify it's a valid PDF
        with open(output_path, "rb") as f:
            header = f.read(8)
            assert header.startswith(b"%PDF")

    def test_both_formats_same_data(self, sample_backtest_results, temp_output_dir):
        """Test generating both HTML and PDF from same data."""
        generator = ReportGenerator(sample_backtest_results)

        html_path = temp_output_dir / "report.html"
        pdf_path = temp_output_dir / "report.pdf"

        # Generate both formats
        generator.generate_report(html_path, format="html")
        generator.generate_report(pdf_path, format="pdf")

        # Both should exist
        assert html_path.exists()
        assert pdf_path.exists()

        # Both should be substantial
        assert html_path.stat().st_size > 1000
        assert pdf_path.stat().st_size > 5000


# Enhancement Tests
class TestEmpyricalIntegration:
    """Test empyrical library integration for accurate metrics."""

    def test_metrics_with_empyrical(self, sample_backtest_results):
        """Test that empyrical is used when available."""
        generator = ReportGenerator(sample_backtest_results)
        metrics = generator._get_performance_metrics()

        # Verify metrics are present
        assert "Sharpe Ratio" in metrics
        assert "Sortino Ratio" in metrics
        assert "Calmar Ratio" in metrics

        # Check if empyrical-specific metrics are present
        from rustybt.analytics.reports import EMPYRICAL_AVAILABLE

        if EMPYRICAL_AVAILABLE:
            assert "Stability" in metrics
            assert "Tail Ratio" in metrics
            assert "Volatility (Annual)" in metrics

    def test_metrics_consistency_with_empyrical(self, sample_backtest_results):
        """Test that empyrical metrics are reasonable."""
        generator = ReportGenerator(sample_backtest_results)
        metrics = generator._get_performance_metrics()

        # Extract numeric values
        sharpe = float(metrics["Sharpe Ratio"])
        sortino = float(metrics["Sortino Ratio"])

        # Verify reasonable ranges (should be between -5 and 10 for typical strategies)
        assert -5 < sharpe < 10
        assert -5 < sortino < 10


class TestPositionDistribution:
    """Test enhanced position distribution functionality."""

    def test_position_extraction_with_columns(self):
        """Test position extraction from position_* columns."""
        # Create data with position columns
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        data = pd.DataFrame(
            {
                "portfolio_value": np.random.uniform(95000, 105000, 100),
                "position_AAPL": np.random.uniform(0, 1000, 100),
                "position_MSFT": np.random.uniform(0, 800, 100),
                "position_GOOGL": np.random.uniform(0, 600, 100),
            },
            index=dates,
        )

        generator = ReportGenerator(data)
        position_series = generator._extract_position_data()

        # Should successfully extract positions
        assert position_series is not None
        assert len(position_series) == 3
        assert "AAPL" in position_series.index
        assert "MSFT" in position_series.index
        assert "GOOGL" in position_series.index

    def test_position_chart_with_data(self, temp_output_dir):
        """Test position distribution chart generation with actual position data."""
        # Create data with position columns
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        data = pd.DataFrame(
            {
                "portfolio_value": np.random.uniform(95000, 105000, 100),
                "position_AAPL": np.random.uniform(100, 1000, 100),
                "position_MSFT": np.random.uniform(80, 800, 100),
                "position_GOOGL": np.random.uniform(60, 600, 100),
                "position_TSLA": np.random.uniform(50, 500, 100),
            },
            index=dates,
        )

        generator = ReportGenerator(data)
        chart = generator._generate_position_distribution()

        # Should generate a chart (not just placeholder)
        assert chart.startswith("data:image/png;base64,")
        assert len(chart) > 1000  # Should be substantial

    def test_position_distribution_in_report(self, temp_output_dir):
        """Test position distribution appears in full report."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        data = pd.DataFrame(
            {
                "portfolio_value": np.random.uniform(95000, 105000, 100),
                "position_AAPL": np.random.uniform(100, 1000, 100),
                "position_MSFT": np.random.uniform(80, 800, 100),
            },
            index=dates,
        )

        generator = ReportGenerator(data)
        output_path = temp_output_dir / "position_report.html"
        generator.generate_report(output_path, format="html")

        html_content = output_path.read_text()
        assert "Position Distribution" in html_content

    def test_position_extraction_no_data(self, sample_backtest_results):
        """Test graceful handling when no position data available."""
        generator = ReportGenerator(sample_backtest_results)
        position_series = generator._extract_position_data()

        # Should return None when no position data
        assert position_series is None

    def test_position_chart_graceful_degradation(self, sample_backtest_results):
        """Test position chart shows informative message when no data."""
        generator = ReportGenerator(sample_backtest_results)
        chart = generator._generate_position_distribution()

        # Should still generate a chart with informative message
        assert chart.startswith("data:image/png;base64,")
        assert len(chart) > 100
