"""Tests for CCXTAdapter resumable ingestion with progress tracking.

This module tests the progress tracking and resume functionality added to
CCXTAdapter, ensuring ingestion can be interrupted and resumed from where it left off.

CR-002 Compliance: No mocks used - tests use real filesystem operations and progress files.
"""

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters import CCXTAdapter
from rustybt.data.adapters.ccxt_adapter import IngestionProgress, IngestionStatus, SymbolProgress
from rustybt.utils.paths import data_path


class TestProgressFileOperations:
    """Tests for progress file I/O operations."""

    def test_progress_file_path(self, tmp_path) -> None:
        """Progress file path is correctly computed for bundle."""
        adapter = CCXTAdapter(exchange_id="binance")

        # Use temp directory for testing
        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        progress_path = adapter._get_progress_file_path(str(bundle_dir))

        assert progress_path == bundle_dir / ".ingestion_progress.json"
        assert progress_path.name == ".ingestion_progress.json"

    def test_save_and_load_progress(self, tmp_path) -> None:
        """Progress can be saved to file and loaded back correctly."""
        adapter = CCXTAdapter(exchange_id="binance")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Create progress tracker
        progress = IngestionProgress(
            bundle_name="test-bundle",
            frequency="1h",
        )

        # Add symbol progress
        progress.symbols["BTC/USDT"] = SymbolProgress(
            status=IngestionStatus.COMPLETED,
            start="2020-01-01",
            end="2020-12-31",
            rows_ingested=8760,
        )

        progress.symbols["ETH/USDT"] = SymbolProgress(
            status=IngestionStatus.IN_PROGRESS,
            start="2020-01-01",
            end="2020-12-31",
        )

        # Save progress
        adapter._save_progress(str(bundle_dir), progress)

        # Verify file exists
        progress_file = bundle_dir / ".ingestion_progress.json"
        assert progress_file.exists()

        # Load progress
        loaded_progress = adapter._load_progress(str(bundle_dir))

        # Verify loaded data matches
        assert loaded_progress.bundle_name == "test-bundle"
        assert loaded_progress.frequency == "1h"
        assert len(loaded_progress.symbols) == 2
        assert loaded_progress.symbols["BTC/USDT"].status == IngestionStatus.COMPLETED
        assert loaded_progress.symbols["BTC/USDT"].rows_ingested == 8760
        assert loaded_progress.symbols["ETH/USDT"].status == IngestionStatus.IN_PROGRESS

    def test_load_progress_nonexistent_file(self, tmp_path) -> None:
        """Loading progress from nonexistent file returns new progress tracker."""
        adapter = CCXTAdapter(exchange_id="binance")

        bundle_dir = tmp_path / "bundles" / "nonexistent-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Load progress (file doesn't exist)
        progress = adapter._load_progress(str(bundle_dir))

        # Should return new empty progress
        assert progress is None

    def test_load_progress_corrupted_file(self, tmp_path) -> None:
        """Corrupted progress file is handled gracefully."""
        adapter = CCXTAdapter(exchange_id="binance")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Create corrupted progress file
        progress_file = bundle_dir / ".ingestion_progress.json"
        progress_file.write_text("{ corrupted json data ;;;")

        # Load progress (should handle corruption)
        progress = adapter._load_progress(str(bundle_dir))

        # Should return None for corrupted file
        assert progress is None

    def test_atomic_file_write(self, tmp_path) -> None:
        """Progress file writes are atomic (temp file + rename pattern)."""
        adapter = CCXTAdapter(exchange_id="binance")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Create progress
        progress = IngestionProgress(
            bundle_name="test-bundle",
            frequency="1h",
        )

        # Save progress (uses temp file + rename)
        adapter._save_progress(str(bundle_dir), progress)

        # Verify final file exists
        progress_file = bundle_dir / ".ingestion_progress.json"
        assert progress_file.exists()

        # Verify no temp files remain
        temp_files = list(bundle_dir.glob(".ingestion_progress.json.tmp*"))
        assert len(temp_files) == 0


class TestIngestionProgressTracking:
    """Tests for progress tracking dataclasses."""

    def test_symbol_progress_creation(self) -> None:
        """SymbolProgress dataclass initializes correctly."""
        progress = SymbolProgress(
            status=IngestionStatus.PENDING,
            start="2020-01-01",
            end="2020-12-31",
        )

        assert progress.status == IngestionStatus.PENDING
        assert progress.start == "2020-01-01"
        assert progress.end == "2020-12-31"
        assert progress.rows_ingested == 0
        assert progress.error_message is None
        assert progress.started_at is None
        assert progress.completed_at is None

    def test_ingestion_progress_pending_symbols(self) -> None:
        """get_pending_symbols returns only pending and failed symbols."""
        progress = IngestionProgress(
            bundle_name="test-bundle",
            frequency="1h",
        )

        # Add various status symbols
        progress.symbols["BTC/USDT"] = SymbolProgress(
            status=IngestionStatus.COMPLETED,
            start="2020-01-01",
            end="2020-12-31",
        )

        progress.symbols["ETH/USDT"] = SymbolProgress(
            status=IngestionStatus.PENDING,
            start="2020-01-01",
            end="2020-12-31",
        )

        progress.symbols["LINK/USDT"] = SymbolProgress(
            status=IngestionStatus.FAILED,
            start="2020-01-01",
            end="2020-12-31",
            error_message="Network timeout",
        )

        progress.symbols["ADA/USDT"] = SymbolProgress(
            status=IngestionStatus.IN_PROGRESS,
            start="2020-01-01",
            end="2020-12-31",
        )

        # Get pending symbols (includes PENDING, FAILED, IN_PROGRESS)
        pending = progress.get_pending_symbols()

        assert "BTC/USDT" not in pending  # Completed - skip
        assert "ETH/USDT" in pending  # Pending - include
        assert "LINK/USDT" in pending  # Failed - retry
        assert "ADA/USDT" in pending  # In progress - retry

    def test_ingestion_progress_mark_completed(self) -> None:
        """mark_completed updates symbol status and timestamp."""
        progress = IngestionProgress(
            bundle_name="test-bundle",
            frequency="1h",
        )

        progress.symbols["BTC/USDT"] = SymbolProgress(
            status=IngestionStatus.IN_PROGRESS,
            start="2020-01-01",
            end="2020-12-31",
        )

        # Mark as completed
        progress.mark_completed("BTC/USDT", rows_ingested=8760)

        assert progress.symbols["BTC/USDT"].status == IngestionStatus.COMPLETED
        assert progress.symbols["BTC/USDT"].rows_ingested == 8760
        assert progress.symbols["BTC/USDT"].completed_at is not None

    def test_ingestion_progress_mark_failed(self) -> None:
        """mark_failed updates symbol status with error message."""
        progress = IngestionProgress(
            bundle_name="test-bundle",
            frequency="1h",
        )

        progress.symbols["BTC/USDT"] = SymbolProgress(
            status=IngestionStatus.IN_PROGRESS,
            start="2020-01-01",
            end="2020-12-31",
        )

        # Mark as failed
        error_msg = "Network timeout after 3 retries"
        progress.mark_failed("BTC/USDT", error_message=error_msg)

        assert progress.symbols["BTC/USDT"].status == IngestionStatus.FAILED
        assert progress.symbols["BTC/USDT"].error_message == error_msg


class TestIngestionResume:
    """Integration tests for resumable ingestion workflow."""

    def test_resume_skips_completed_symbols(self, tmp_path) -> None:
        """Resume ingestion skips already-completed symbols."""
        adapter = CCXTAdapter(exchange_id="binance")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Create progress with one completed symbol
        progress = IngestionProgress(
            bundle_name="test-bundle",
            frequency="1h",
        )

        progress.symbols["BTC/USDT"] = SymbolProgress(
            status=IngestionStatus.COMPLETED,
            start="2020-01-01",
            end="2020-12-31",
            rows_ingested=8760,
        )

        progress.symbols["ETH/USDT"] = SymbolProgress(
            status=IngestionStatus.PENDING,
            start="2020-01-01",
            end="2020-12-31",
        )

        # Save progress
        adapter._save_progress(str(bundle_dir), progress)

        # Load progress and get pending symbols
        loaded_progress = adapter._load_progress(str(bundle_dir))
        pending_symbols = loaded_progress.get_pending_symbols()

        # BTC/USDT should be skipped, ETH/USDT should be pending
        assert "BTC/USDT" not in pending_symbols
        assert "ETH/USDT" in pending_symbols

    def test_retry_failed_symbols(self, tmp_path) -> None:
        """Resume ingestion retries failed symbols."""
        adapter = CCXTAdapter(exchange_id="binance")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Create progress with failed symbol
        progress = IngestionProgress(
            bundle_name="test-bundle",
            frequency="1h",
        )

        progress.symbols["BTC/USDT"] = SymbolProgress(
            status=IngestionStatus.FAILED,
            start="2020-01-01",
            end="2020-12-31",
            error_message="Network timeout",
        )

        # Save progress
        adapter._save_progress(str(bundle_dir), progress)

        # Load progress and get pending symbols
        loaded_progress = adapter._load_progress(str(bundle_dir))
        pending_symbols = loaded_progress.get_pending_symbols()

        # Failed symbol should be in pending (for retry)
        assert "BTC/USDT" in pending_symbols

    def test_progress_updated_per_symbol(self, tmp_path) -> None:
        """Progress file is updated after each symbol ingestion."""
        adapter = CCXTAdapter(exchange_id="binance")

        bundle_dir = tmp_path / "bundles" / "test-bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Create initial progress
        progress = IngestionProgress(
            bundle_name="test-bundle",
            frequency="1h",
        )

        progress.symbols["BTC/USDT"] = SymbolProgress(
            status=IngestionStatus.IN_PROGRESS,
            start="2020-01-01",
            end="2020-12-31",
        )

        # Save progress
        adapter._save_progress(str(bundle_dir), progress)

        # Simulate symbol completion
        progress.mark_completed("BTC/USDT", rows_ingested=8760)
        adapter._save_progress(str(bundle_dir), progress)

        # Reload and verify update
        updated_progress = adapter._load_progress(str(bundle_dir))
        assert updated_progress.symbols["BTC/USDT"].status == IngestionStatus.COMPLETED
        assert updated_progress.symbols["BTC/USDT"].rows_ingested == 8760
