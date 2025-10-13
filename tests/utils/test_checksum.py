"""Tests for checksum calculation utilities."""

import tempfile
from pathlib import Path

import pytest

from rustybt.utils.checksum import calculate_checksum, calculate_checksum_multiple


class TestChecksumCalculation:
    """Test checksum calculation for single files."""

    def test_checksum_calculation(self):
        """Test SHA256 checksum calculation with known data."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test data")
            filepath = f.name

        try:
            checksum = calculate_checksum(filepath)

            # Verify checksum is valid SHA256 (64 hex chars)
            assert len(checksum) == 64
            assert all(c in "0123456789abcdef" for c in checksum)

            # Verify deterministic - same file gives same checksum
            checksum2 = calculate_checksum(filepath)
            assert checksum == checksum2
        finally:
            Path(filepath).unlink()

    def test_checksum_empty_file(self):
        """Test checksum of empty file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            filepath = f.name

        try:
            checksum = calculate_checksum(filepath)
            assert len(checksum) == 64
            # Empty file has known SHA256 hash
            assert checksum == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        finally:
            Path(filepath).unlink()

    def test_checksum_large_file(self):
        """Test checksum calculation for large file (>8KB chunks)."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            # Write 100KB of data
            data = b"x" * 100000
            f.write(data)
            filepath = f.name

        try:
            checksum = calculate_checksum(filepath)
            assert len(checksum) == 64
            assert all(c in "0123456789abcdef" for c in checksum)
        finally:
            Path(filepath).unlink()

    def test_checksum_different_files_different_hashes(self):
        """Test that different content produces different checksums."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f1:
            f1.write("test data 1")
            filepath1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f2:
            f2.write("test data 2")
            filepath2 = f2.name

        try:
            checksum1 = calculate_checksum(filepath1)
            checksum2 = calculate_checksum(filepath2)
            assert checksum1 != checksum2
        finally:
            Path(filepath1).unlink()
            Path(filepath2).unlink()

    def test_checksum_file_not_found(self):
        """Test error handling for missing file."""
        with pytest.raises(FileNotFoundError):
            calculate_checksum("/nonexistent/file.txt")


class TestChecksumMultiple:
    """Test checksum calculation for multiple files."""

    def test_checksum_multiple_files(self):
        """Test combined checksum of multiple files."""
        files = []
        try:
            for i in range(3):
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                    f.write(f"test data {i}")
                    files.append(f.name)

            checksum = calculate_checksum_multiple(files)
            assert len(checksum) == 64
            assert all(c in "0123456789abcdef" for c in checksum)

            # Verify deterministic
            checksum2 = calculate_checksum_multiple(files)
            assert checksum == checksum2
        finally:
            for filepath in files:
                Path(filepath).unlink()

    def test_checksum_multiple_order_independent(self):
        """Test that file order is deterministic (sorted internally)."""
        files = []
        try:
            for i in range(3):
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                    f.write(f"test data {i}")
                    files.append(f.name)

            # Calculate with original order
            checksum1 = calculate_checksum_multiple(files)

            # Calculate with reversed order (should be same due to internal sorting)
            checksum2 = calculate_checksum_multiple(files[::-1])

            assert checksum1 == checksum2
        finally:
            for filepath in files:
                Path(filepath).unlink()

    def test_checksum_multiple_missing_file(self):
        """Test error handling when one file is missing."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test data")
            filepath = f.name

        try:
            files = [filepath, "/nonexistent/file.txt"]
            with pytest.raises(FileNotFoundError):
                calculate_checksum_multiple(files)
        finally:
            Path(filepath).unlink()

    def test_checksum_multiple_empty_list(self):
        """Test checksum of empty file list."""
        checksum = calculate_checksum_multiple([])
        # Empty input gives empty SHA256 hash
        assert checksum == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
