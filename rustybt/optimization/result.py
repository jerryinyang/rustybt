"""Optimization result data structures."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class OptimizationResult:
    """Single optimization trial result."""

    trial_id: int
    params: dict[str, Any]
    score: Decimal
    timestamp: datetime
    backtest_metrics: dict[str, Any]
    error: str | None = None
    duration_seconds: Decimal = Decimal("0")

    def __post_init__(self):
        """Validate result after initialization."""
        # Convert score to Decimal if needed
        if not isinstance(self.score, Decimal):
            object.__setattr__(self, "score", Decimal(str(self.score)))

        # Convert duration to Decimal if needed
        if not isinstance(self.duration_seconds, Decimal):
            object.__setattr__(self, "duration_seconds", Decimal(str(self.duration_seconds)))

        # Validate failed trials have -Infinity score
        if self.error is not None:
            expected_score = Decimal("-Infinity")
            if self.score != expected_score:
                raise ValueError(f"Failed trials must have score=-Infinity, got {self.score}")

    @property
    def is_success(self) -> bool:
        """Check if trial succeeded.

        Returns:
            True if no error occurred
        """
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        # Convert params with potential Decimal values to strings
        serialized_params = {}
        for key, value in self.params.items():
            if isinstance(value, Decimal):
                serialized_params[key] = str(value)
            else:
                serialized_params[key] = value

        return {
            "trial_id": self.trial_id,
            "params": serialized_params,
            "score": str(self.score),
            "timestamp": self.timestamp.isoformat(),
            "backtest_metrics": self.backtest_metrics,
            "error": self.error,
            "duration_seconds": str(self.duration_seconds),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OptimizationResult":
        """Create from dictionary.

        Args:
            data: Dictionary from to_dict()

        Returns:
            OptimizationResult instance
        """
        return cls(
            trial_id=data["trial_id"],
            params=data["params"],
            score=Decimal(data["score"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            backtest_metrics=data["backtest_metrics"],
            error=data.get("error"),
            duration_seconds=Decimal(data.get("duration_seconds", "0")),
        )
