"""State management for live trading crash recovery.

This module implements checkpoint-based state persistence with atomic writes,
staleness detection, and position reconciliation for crash recovery.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import structlog

from rustybt.live.models import ReconciliationStrategy, StateCheckpoint

logger = structlog.get_logger(__name__)


class StateError(Exception):
    """Base exception for state management errors."""


class CheckpointCorrupted(StateError):
    """Raised when checkpoint file is corrupted or invalid."""


class StateManager:
    """Manages state checkpointing and restoration for crash recovery.

    Provides atomic checkpoint writes, staleness detection, and integration
    with live trading engine for periodic state persistence.

    Attributes:
        checkpoint_dir: Directory for storing checkpoint files
        staleness_threshold_seconds: Threshold for stale checkpoint warnings
    """

    def __init__(
        self,
        checkpoint_dir: Path | None = None,
        staleness_threshold_seconds: int = 3600,
    ):
        """Initialize StateManager.

        Args:
            checkpoint_dir: Directory for checkpoint storage
                (default: ~/.rustybt/state/)
            staleness_threshold_seconds: Staleness threshold in seconds
                (default: 3600 = 1 hour)
        """
        if checkpoint_dir is None:
            checkpoint_dir = Path.home() / ".rustybt" / "state"

        self.checkpoint_dir = Path(checkpoint_dir)
        self.staleness_threshold_seconds = staleness_threshold_seconds

        # Create checkpoint directory if it doesn't exist
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "state_manager_initialized",
            checkpoint_dir=str(self.checkpoint_dir),
            staleness_threshold_seconds=staleness_threshold_seconds,
        )

    def _get_checkpoint_path(self, strategy_name: str) -> Path:
        """Get checkpoint file path for strategy.

        Args:
            strategy_name: Strategy identifier

        Returns:
            Path to checkpoint file
        """
        # Sanitize strategy name to prevent directory traversal
        safe_name = "".join(c for c in strategy_name if c.isalnum() or c in ("_", "-"))
        return self.checkpoint_dir / f"{safe_name}_checkpoint.json"

    def _get_temp_path(self, checkpoint_path: Path) -> Path:
        """Get temporary file path for atomic writes.

        Args:
            checkpoint_path: Final checkpoint file path

        Returns:
            Path to temporary file
        """
        return checkpoint_path.with_suffix(".tmp")

    def save_checkpoint(self, strategy_name: str, state: StateCheckpoint) -> None:
        """Save state checkpoint with atomic write guarantees.

        Uses temp file + rename pattern to ensure atomicity and prevent
        corruption from interrupted writes.

        Args:
            strategy_name: Strategy identifier
            state: State checkpoint to save

        Raises:
            StateError: If checkpoint write fails
        """
        checkpoint_path = self._get_checkpoint_path(strategy_name)
        temp_path = self._get_temp_path(checkpoint_path)

        try:
            # Write to temporary file first
            with open(temp_path, "w") as f:
                # Use Pydantic's JSON serialization with datetime handling
                json_data = state.model_dump_json(indent=2)
                f.write(json_data)
                f.flush()
                os.fsync(f.fileno())  # Ensure data written to disk

            # Atomic rename (overwrites existing checkpoint)
            os.rename(temp_path, checkpoint_path)

            logger.info(
                "checkpoint_saved",
                strategy_name=strategy_name,
                checkpoint_path=str(checkpoint_path),
                timestamp=state.timestamp.isoformat(),
                positions_count=len(state.positions),
                pending_orders_count=len(state.pending_orders),
                cash_balance=state.cash_balance,
            )

        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()

            logger.error(
                "checkpoint_save_failed",
                strategy_name=strategy_name,
                error=str(e),
                exc_info=True,
            )
            raise StateError(f"Failed to save checkpoint for {strategy_name}: {e}") from e

    def load_checkpoint(self, strategy_name: str) -> StateCheckpoint | None:
        """Load state checkpoint from disk.

        Args:
            strategy_name: Strategy identifier

        Returns:
            StateCheckpoint if found and valid, None if not found

        Raises:
            CheckpointCorrupted: If checkpoint exists but is invalid
        """
        checkpoint_path = self._get_checkpoint_path(strategy_name)

        if not checkpoint_path.exists():
            logger.info(
                "checkpoint_not_found",
                strategy_name=strategy_name,
                checkpoint_path=str(checkpoint_path),
            )
            return None

        try:
            with open(checkpoint_path) as f:
                json_data = f.read()

            # Parse and validate using Pydantic
            checkpoint = StateCheckpoint.model_validate_json(json_data)

            # Check staleness
            if checkpoint.is_stale(self.staleness_threshold_seconds):
                age_hours = (
                    datetime.now() - checkpoint.timestamp.replace(tzinfo=None)
                ).total_seconds() / 3600
                logger.warning(
                    "checkpoint_stale",
                    strategy_name=strategy_name,
                    checkpoint_age_hours=age_hours,
                    threshold_hours=self.staleness_threshold_seconds / 3600,
                    timestamp=checkpoint.timestamp.isoformat(),
                )

            logger.info(
                "checkpoint_loaded",
                strategy_name=strategy_name,
                timestamp=checkpoint.timestamp.isoformat(),
                positions_count=len(checkpoint.positions),
                pending_orders_count=len(checkpoint.pending_orders),
                cash_balance=checkpoint.cash_balance,
            )

            return checkpoint

        except json.JSONDecodeError as e:
            logger.error(
                "checkpoint_corrupted",
                strategy_name=strategy_name,
                error="Invalid JSON",
                exc_info=True,
            )
            raise CheckpointCorrupted(
                f"Checkpoint for {strategy_name} is corrupted (invalid JSON): {e}"
            ) from e

        except Exception as e:
            logger.error(
                "checkpoint_load_failed",
                strategy_name=strategy_name,
                error=str(e),
                exc_info=True,
            )
            raise CheckpointCorrupted(f"Failed to load checkpoint for {strategy_name}: {e}") from e

    def delete_checkpoint(self, strategy_name: str) -> bool:
        """Delete checkpoint file for strategy.

        Args:
            strategy_name: Strategy identifier

        Returns:
            True if checkpoint was deleted, False if it didn't exist
        """
        checkpoint_path = self._get_checkpoint_path(strategy_name)

        if checkpoint_path.exists():
            checkpoint_path.unlink()
            logger.info(
                "checkpoint_deleted",
                strategy_name=strategy_name,
                checkpoint_path=str(checkpoint_path),
            )
            return True

        return False

    def list_checkpoints(self) -> list[str]:
        """List all available checkpoint strategy names.

        Returns:
            List of strategy names with checkpoints
        """
        checkpoints = []

        for path in self.checkpoint_dir.glob("*_checkpoint.json"):
            # Extract strategy name from filename
            strategy_name = path.stem.replace("_checkpoint", "")
            checkpoints.append(strategy_name)

        return sorted(checkpoints)

    def get_checkpoint_info(self, strategy_name: str) -> dict | None:
        """Get checkpoint metadata without loading full state.

        Args:
            strategy_name: Strategy identifier

        Returns:
            Dict with checkpoint metadata or None if not found
        """
        checkpoint_path = self._get_checkpoint_path(strategy_name)

        if not checkpoint_path.exists():
            return None

        try:
            stat = checkpoint_path.stat()

            # Quick JSON parse for timestamp only
            with open(checkpoint_path) as f:
                data = json.load(f)

            return {
                "strategy_name": strategy_name,
                "file_path": str(checkpoint_path),
                "file_size_bytes": stat.st_size,
                "file_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "checkpoint_timestamp": data.get("timestamp"),
                "positions_count": len(data.get("positions", [])),
                "pending_orders_count": len(data.get("pending_orders", [])),
            }

        except Exception as e:
            logger.warning(
                "checkpoint_info_failed",
                strategy_name=strategy_name,
                error=str(e),
            )
            return None

    def get_alignment_history(
        self,
        strategy_name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list:
        """Get historical alignment metrics from checkpoints.

        Args:
            strategy_name: Strategy identifier
            start_time: Start of time range (optional)
            end_time: End of time range (optional)

        Returns:
            List of alignment metrics dictionaries

        Raises:
            StateError: If checkpoint loading fails
        """
        checkpoint = self.load_checkpoint(strategy_name)
        if not checkpoint:
            return []

        # For now, return current checkpoint's alignment metrics
        # In a full implementation, this would query multiple checkpoint files
        if checkpoint.alignment_metrics:
            # Filter by time range if provided
            checkpoint_time = checkpoint.timestamp
            if start_time and checkpoint_time < start_time:
                return []
            if end_time and checkpoint_time > end_time:
                return []

            return [checkpoint.alignment_metrics.model_dump()]

        return []

    def export_alignment_csv(
        self,
        strategy_name: str,
        filepath: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> None:
        """Export alignment history to CSV file.

        Args:
            strategy_name: Strategy identifier
            filepath: Output CSV file path
            start_time: Start of time range (optional)
            end_time: End of time range (optional)

        Raises:
            StateError: If export fails
        """
        import csv

        history = self.get_alignment_history(strategy_name, start_time, end_time)

        if not history:
            logger.warning(
                "no_alignment_data_to_export",
                strategy_name=strategy_name,
            )
            return

        try:
            with open(filepath, "w", newline="") as f:
                # Get all possible fields from first record
                fieldnames = list(history[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                writer.writeheader()
                for record in history:
                    # Flatten nested dicts for CSV
                    flat_record = {}
                    for key, value in record.items():
                        if isinstance(value, dict):
                            for subkey, subvalue in value.items():
                                flat_record[f"{key}_{subkey}"] = str(subvalue)
                        else:
                            flat_record[key] = str(value)
                    writer.writerow(flat_record)

            logger.info(
                "alignment_history_exported",
                strategy_name=strategy_name,
                filepath=filepath,
                record_count=len(history),
            )

        except Exception as e:
            raise StateError(f"Failed to export alignment history: {e}") from e
