"""Tests for alignment dashboard."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from rustybt.live.shadow.dashboard import AlignmentDashboard
from rustybt.live.shadow.models import SignalAlignment


class TestAlignmentDashboard:
    """Test suite for AlignmentDashboard."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create mock StateManager."""
        manager = MagicMock()
        manager.get_alignment_history = MagicMock(return_value=[])
        return manager

    @pytest.fixture
    def dashboard(self, mock_state_manager):
        """Create dashboard instance."""
        return AlignmentDashboard(
            state_manager=mock_state_manager,
            strategy_name="test_strategy",
        )

    def test_initialization(self, dashboard, mock_state_manager):
        """Test dashboard initialization."""
        assert dashboard.state_manager == mock_state_manager
        assert dashboard.strategy_name == "test_strategy"

    def test_get_signal_match_rate_empty_history(self, dashboard, mock_state_manager):
        """Test signal match rate with no history."""
        mock_state_manager.get_alignment_history.return_value = []

        match_rate, divergence = dashboard.get_signal_match_rate()

        assert match_rate == Decimal("0.0")
        assert divergence == {}

    def test_get_signal_match_rate_with_data(self, dashboard, mock_state_manager):
        """Test signal match rate calculation with data."""
        mock_state_manager.get_alignment_history.return_value = [
            {
                "signal_alignment": {
                    "backtest_signal_count": 10,
                    "live_signal_count": 9,
                    "signal_match_rate": "0.80",
                    "divergence_breakdown": {
                        SignalAlignment.EXACT_MATCH.value: 8,
                        SignalAlignment.DIRECTION_MATCH.value: 1,
                        SignalAlignment.MISSING_SIGNAL.value: 1,
                    },
                }
            },
            {
                "signal_alignment": {
                    "backtest_signal_count": 5,
                    "live_signal_count": 5,
                    "signal_match_rate": "1.00",
                    "divergence_breakdown": {
                        SignalAlignment.EXACT_MATCH.value: 5,
                    },
                }
            },
        ]

        match_rate, divergence = dashboard.get_signal_match_rate()

        # Total: 13 exact matches out of 15 backtest signals
        assert match_rate == Decimal("13") / Decimal("15")
        assert divergence[SignalAlignment.EXACT_MATCH.value] == 13
        assert divergence[SignalAlignment.DIRECTION_MATCH.value] == 1
        assert divergence[SignalAlignment.MISSING_SIGNAL.value] == 1

    def test_get_execution_quality_metrics_empty_history(self, dashboard, mock_state_manager):
        """Test execution quality metrics with no history."""
        mock_state_manager.get_alignment_history.return_value = []

        metrics = dashboard.get_execution_quality_metrics()

        assert metrics["expected_slippage_bps"] == Decimal("0")
        assert metrics["actual_slippage_bps"] == Decimal("0")
        assert metrics["slippage_error_bps"] == Decimal("0")

    def test_get_execution_quality_metrics_with_data(self, dashboard, mock_state_manager):
        """Test execution quality metrics calculation."""
        mock_state_manager.get_alignment_history.return_value = [
            {
                "execution_quality": {
                    "expected_slippage_bps": "5.0",
                    "actual_slippage_bps": "6.5",
                    "slippage_error_bps": "1.5",
                    "fill_rate_expected": "1.0",
                    "fill_rate_actual": "0.95",
                    "commission_expected": "10.0",
                    "commission_actual": "11.0",
                }
            },
            {
                "execution_quality": {
                    "expected_slippage_bps": "3.0",
                    "actual_slippage_bps": "4.0",
                    "slippage_error_bps": "1.0",
                    "fill_rate_expected": "1.0",
                    "fill_rate_actual": "0.90",
                    "commission_expected": "10.0",
                    "commission_actual": "12.0",
                }
            },
        ]

        metrics = dashboard.get_execution_quality_metrics()

        # Averages of the two samples
        assert metrics["expected_slippage_bps"] == Decimal("4.0")
        assert metrics["actual_slippage_bps"] == Decimal("5.25")
        assert metrics["slippage_error_bps"] == Decimal("1.25")
        assert metrics["fill_rate_expected"] == Decimal("1.0")
        assert metrics["fill_rate_actual"] == Decimal("0.925")

    def test_get_execution_quality_metrics_with_none_values(self, dashboard, mock_state_manager):
        """Test execution quality metrics handles None values."""
        mock_state_manager.get_alignment_history.return_value = [
            {"execution_quality": None},
            {
                "execution_quality": {
                    "expected_slippage_bps": "5.0",
                    "actual_slippage_bps": "6.0",
                    "slippage_error_bps": "1.0",
                    "fill_rate_expected": "1.0",
                    "fill_rate_actual": "1.0",
                    "commission_expected": "10.0",
                    "commission_actual": "10.0",
                }
            },
        ]

        metrics = dashboard.get_execution_quality_metrics()

        # Should only use the non-None sample
        assert metrics["expected_slippage_bps"] == Decimal("5.0")
        assert metrics["actual_slippage_bps"] == Decimal("6.0")

    def test_get_pnl_comparison(self, dashboard, mock_state_manager):
        """Test P&L comparison (not yet implemented)."""
        result = dashboard.get_pnl_comparison()

        assert "cumulative" in result
        assert "daily" in result
        assert result["cumulative"] == []
        assert result["daily"] == []

    def test_get_circuit_breaker_status(self, dashboard):
        """Test circuit breaker status (not yet integrated)."""
        status = dashboard.get_circuit_breaker_status()

        assert "status" in status
        assert status["status"] == "UNKNOWN"

    def test_get_alignment_trend_default_periods(self, dashboard, mock_state_manager):
        """Test alignment trend with default periods."""
        mock_state_manager.get_alignment_history.return_value = [
            {
                "signal_alignment": {
                    "backtest_signal_count": 10,
                    "live_signal_count": 10,
                    "signal_match_rate": "1.0",
                    "divergence_breakdown": {
                        SignalAlignment.EXACT_MATCH.value: 10,
                    },
                },
                "execution_quality": {
                    "expected_slippage_bps": "5.0",
                    "actual_slippage_bps": "5.0",
                    "slippage_error_bps": "0.0",
                    "fill_rate_expected": "1.0",
                    "fill_rate_actual": "1.0",
                    "commission_expected": "10.0",
                    "commission_actual": "10.0",
                },
            }
        ]

        trends = dashboard.get_alignment_trend()

        assert "1h" in trends
        assert "24h" in trends
        assert "7d" in trends
        assert "30d" in trends

        # Verify structure of trend data
        for period, metrics in trends.items():
            assert "signal_match_rate" in metrics
            assert "avg_slippage_error_bps" in metrics
            assert "avg_fill_rate_error_pct" in metrics

    def test_get_alignment_trend_custom_periods(self, dashboard, mock_state_manager):
        """Test alignment trend with custom periods."""
        mock_state_manager.get_alignment_history.return_value = []

        custom_periods = [timedelta(minutes=30), timedelta(hours=2)]
        trends = dashboard.get_alignment_trend(periods=custom_periods)

        # Should have entries for custom periods
        assert len(trends) == 2

    def test_export_dashboard_json(self, dashboard, mock_state_manager):
        """Test JSON export of dashboard data."""
        mock_state_manager.get_alignment_history.return_value = [
            {
                "signal_alignment": {
                    "backtest_signal_count": 5,
                    "live_signal_count": 5,
                    "signal_match_rate": "1.0",
                    "divergence_breakdown": {
                        SignalAlignment.EXACT_MATCH.value: 5,
                    },
                },
                "execution_quality": {
                    "expected_slippage_bps": "5.0",
                    "actual_slippage_bps": "5.0",
                    "slippage_error_bps": "0.0",
                    "fill_rate_expected": "1.0",
                    "fill_rate_actual": "1.0",
                    "commission_expected": "10.0",
                    "commission_actual": "10.0",
                },
            }
        ]

        json_data = dashboard.export_dashboard_json()

        # Verify structure
        assert "timestamp" in json_data
        assert "time_window_seconds" in json_data
        assert "signal_alignment" in json_data
        assert "execution_quality" in json_data
        assert "pnl_comparison" in json_data
        assert "circuit_breaker" in json_data
        assert "trends" in json_data

        # Verify all Decimal values are converted to strings
        assert isinstance(json_data["signal_alignment"]["match_rate"], str)
        assert isinstance(
            json_data["execution_quality"]["expected_slippage_bps"],
            str,
        )

    def test_time_window_parameter_used(self, dashboard, mock_state_manager):
        """Test that time_window parameter is passed to state_manager."""
        custom_window = timedelta(hours=2)
        dashboard.get_signal_match_rate(time_window=custom_window)

        # Verify state_manager was called with correct time range
        call_args = mock_state_manager.get_alignment_history.call_args
        assert call_args is not None

        # Check that start_time and end_time span the custom window
        kwargs = call_args[1]
        start_time = kwargs["start_time"]
        end_time = kwargs["end_time"]
        time_diff = end_time - start_time

        # Allow small tolerance for execution time
        assert abs((time_diff - custom_window).total_seconds()) < 1.0

    def test_fill_rate_error_calculation(self, dashboard, mock_state_manager):
        """Test fill rate error percentage calculation."""
        mock_state_manager.get_alignment_history.return_value = [
            {
                "execution_quality": {
                    "expected_slippage_bps": "5.0",
                    "actual_slippage_bps": "5.0",
                    "slippage_error_bps": "0.0",
                    "fill_rate_expected": "1.0",
                    "fill_rate_actual": "0.9",  # 10% worse
                    "commission_expected": "10.0",
                    "commission_actual": "10.0",
                }
            }
        ]

        metrics = dashboard.get_execution_quality_metrics()

        # Fill rate error should be -10%
        expected_error = (Decimal("0.9") - Decimal("1.0")) / Decimal("1.0") * Decimal("100")
        assert metrics["fill_rate_error_pct"] == expected_error

    def test_commission_error_calculation(self, dashboard, mock_state_manager):
        """Test commission error percentage calculation."""
        mock_state_manager.get_alignment_history.return_value = [
            {
                "execution_quality": {
                    "expected_slippage_bps": "5.0",
                    "actual_slippage_bps": "5.0",
                    "slippage_error_bps": "0.0",
                    "fill_rate_expected": "1.0",
                    "fill_rate_actual": "1.0",
                    "commission_expected": "10.0",
                    "commission_actual": "12.0",  # 20% higher
                }
            }
        ]

        metrics = dashboard.get_execution_quality_metrics()

        # Commission error should be +20%
        expected_error = (Decimal("12.0") - Decimal("10.0")) / Decimal("10.0") * Decimal("100")
        assert metrics["commission_error_pct"] == expected_error
