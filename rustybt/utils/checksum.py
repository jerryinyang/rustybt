"""Checksum calculation utilities for data provenance tracking."""

import hashlib
from pathlib import Path


def calculate_checksum(file_path: str | Path) -> str:
    """Calculate SHA256 checksum of a file.

    Args:
        file_path: Path to the file to checksum

    Returns:
        SHA256 checksum as hexadecimal string (64 characters)

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256_hash = hashlib.sha256()

    # Read file in chunks to handle large files efficiently
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def calculate_checksum_multiple(file_paths: list[str | Path]) -> str:
    """Calculate combined SHA256 checksum for multiple files.

    Args:
        file_paths: List of file paths to checksum

    Returns:
        SHA256 checksum of concatenated file contents

    Raises:
        FileNotFoundError: If any file does not exist
        PermissionError: If any file cannot be read
    """
    sha256_hash = hashlib.sha256()

    for file_path in sorted(file_paths):  # Sort for deterministic ordering
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

    return sha256_hash.hexdigest()
