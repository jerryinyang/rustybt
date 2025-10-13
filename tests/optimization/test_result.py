"""Tests for optimization result data structures."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.optimization.result import OptimizationResult


class TestOptimizationResult:
    """Tests for OptimizationResult."""

    def test_valid_result(self):
        """Test creating valid optimization result."""
        result = OptimizationResult(
            trial_id=0,
            params={"lr": 0.01, "window": 20},
            score=Decimal("1.5"),
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            backtest_metrics={"sharpe_ratio": 1.5, "total_return": 0.25},
            duration_seconds=Decimal("45.5"),
        )

        assert result.trial_id == 0
        assert result.params == {"lr": 0.01, "window": 20}
        assert result.score == Decimal("1.5")
        assert result.error is None
        assert result.is_success is True

    def test_failed_result(self):
        """Test creating failed optimization result."""
        result = OptimizationResult(
            trial_id=1,
            params={"lr": 0.01},
            score=Decimal("-Infinity"),
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            backtest_metrics={},
            error="Backtest failed: invalid parameters",
            duration_seconds=Decimal("2.5"),
        )

        assert result.error is not None
        assert result.is_success is False
        assert result.score == Decimal("-Infinity")

    def test_failed_result_without_negative_infinity_raises(self):
        """Test failed result without -Infinity score raises error."""
        with pytest.raises(ValueError) as exc_info:
            OptimizationResult(
                trial_id=1,
                params={"lr": 0.01},
                score=Decimal("1.5"),  # Should be -Infinity
                timestamp=datetime(2025, 1, 1, 12, 0, 0),
                backtest_metrics={},
                error="Backtest failed",
            )

        assert "-Infinity" in str(exc_info.value)

    def test_auto_convert_score_to_decimal(self):
        """Test score is automatically converted to Decimal."""
        result = OptimizationResult(
            trial_id=0,
            params={},
            score=1.5,  # Float, not Decimal
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            backtest_metrics={},
        )

        assert isinstance(result.score, Decimal)
        assert result.score == Decimal("1.5")

    def test_auto_convert_duration_to_decimal(self):
        """Test duration_seconds is automatically converted to Decimal."""
        result = OptimizationResult(
            trial_id=0,
            params={},
            score=Decimal("1.5"),
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            backtest_metrics={},
            duration_seconds=45.5,  # Float, not Decimal
        )

        assert isinstance(result.duration_seconds, Decimal)
        assert result.duration_seconds == Decimal("45.5")

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = OptimizationResult(
            trial_id=5,
            params={"lr": Decimal("0.01"), "window": 20},
            score=Decimal("2.5"),
            timestamp=datetime(2025, 1, 15, 10, 30, 45),
            backtest_metrics={"sharpe_ratio": 2.5},
            duration_seconds=Decimal("30.5"),
        )

        result_dict = result.to_dict()

        assert result_dict["trial_id"] == 5
        # Decimal params are serialized to strings
        assert result_dict["params"] == {"lr": "0.01", "window": 20}
        assert result_dict["score"] == "2.5"
        assert result_dict["timestamp"] == "2025-01-15T10:30:45"
        assert result_dict["backtest_metrics"] == {"sharpe_ratio": 2.5}
        assert result_dict["error"] is None
        assert result_dict["duration_seconds"] == "30.5"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "trial_id": 5,
            "params": {"lr": 0.01, "window": 20},
            "score": "2.5",
            "timestamp": "2025-01-15T10:30:45",
            "backtest_metrics": {"sharpe_ratio": 2.5},
            "error": None,
            "duration_seconds": "30.5",
        }

        result = OptimizationResult.from_dict(data)

        assert result.trial_id == 5
        assert result.params == {"lr": 0.01, "window": 20}
        assert result.score == Decimal("2.5")
        assert result.timestamp == datetime(2025, 1, 15, 10, 30, 45)
        assert result.error is None
        assert result.duration_seconds == Decimal("30.5")

    def test_round_trip_serialization(self):
        """Test round-trip serialization (to_dict then from_dict)."""
        original = OptimizationResult(
            trial_id=10,
            params={"param1": Decimal("0.5"), "param2": "value"},
            score=Decimal("3.14159"),
            timestamp=datetime(2025, 2, 20, 15, 45, 30),
            backtest_metrics={"metric1": 1.5, "metric2": 2.5},
            duration_seconds=Decimal("120.75"),
        )

        # Convert to dict and back
        result_dict = original.to_dict()
        restored = OptimizationResult.from_dict(result_dict)

        assert restored.trial_id == original.trial_id
        # Note: params won't be exactly equal due to serialization
        # Decimal params are serialized to strings and remain strings after deserialization
        assert restored.params == {"param1": "0.5", "param2": "value"}
        assert restored.score == original.score
        assert restored.timestamp == original.timestamp
        assert restored.backtest_metrics == original.backtest_metrics
        assert restored.error == original.error
        assert restored.duration_seconds == original.duration_seconds

    def test_immutable(self):
        """Test OptimizationResult is immutable (frozen dataclass)."""
        result = OptimizationResult(
            trial_id=0,
            params={},
            score=Decimal("1.0"),
            timestamp=datetime.now(),
            backtest_metrics={},
        )

        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            result.score = Decimal("2.0")

        with pytest.raises(AttributeError):
            result.trial_id = 1
