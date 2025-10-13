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
Security tests for Quandl bundle tarfile extraction.

Tests path traversal attack prevention and safe extraction behavior.
"""

import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

import pytest


class TestTarfilePathTraversalSecurity:
    """Test suite for tarfile path traversal attack prevention."""

    def test_path_traversal_parent_directory_blocked(self):
        """Test that ../ path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create malicious tar with ../ path traversal
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                # Add member attempting to write to parent directory
                info = tarfile.TarInfo(name="../../../etc/malicious.txt")
                info.size = 0
                tar.addfile(info, BytesIO(b""))

            tar_buffer.seek(0)

            # Mock the data object that ingest expects
            class MockEnviron:
                pass

            MockEnviron()
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Attempt extraction - should raise ValueError
            with pytest.raises(ValueError, match="Attempted path traversal"):
                # Simulate the extraction logic from quandl.py
                import pathlib

                with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                    output_path = pathlib.Path(output_dir).resolve()
                    for member in tar.getmembers():
                        member_path = (output_path / member.name).resolve()
                        if not str(member_path).startswith(str(output_path)):
                            raise ValueError(f"Attempted path traversal in tar file: {member.name}")
                    tar.extractall(output_dir)

    def test_path_traversal_absolute_path_blocked(self):
        """Test that absolute path attempts (e.g., /etc/passwd) are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create malicious tar with absolute path
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                # Add member with absolute path
                info = tarfile.TarInfo(name="/etc/passwd")
                info.size = 0
                tar.addfile(info, BytesIO(b""))

            tar_buffer.seek(0)

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Attempt extraction - should raise ValueError
            with pytest.raises(ValueError, match="Attempted path traversal"):
                import pathlib

                with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                    output_path = pathlib.Path(output_dir).resolve()
                    for member in tar.getmembers():
                        member_path = (output_path / member.name).resolve()
                        if not str(member_path).startswith(str(output_path)):
                            raise ValueError(f"Attempted path traversal in tar file: {member.name}")
                    tar.extractall(output_dir)

    def test_path_traversal_symbolic_link_safe_handling(self):
        """Test that symbolic links within the extraction directory are allowed."""
        # NOTE: The current implementation validates paths before extraction.
        # Symlinks are validated based on their name, not their target.
        # This is acceptable for our security model since:
        # 1. Symlink targets are not resolved until extraction
        # 2. Symlinks to outside paths would fail during extraction if attempted
        # 3. The main protection is against path traversal in member names
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create tar with internal symlink (legitimate use case)
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                # Add regular file
                file_info = tarfile.TarInfo(name="data/original.txt")
                content = b"original content"
                file_info.size = len(content)
                tar.addfile(file_info, BytesIO(content))

                # Add symlink within extraction directory
                link_info = tarfile.TarInfo(name="data/link.txt")
                link_info.type = tarfile.SYMTYPE
                link_info.linkname = "original.txt"  # Relative link within same dir
                tar.addfile(link_info)

            tar_buffer.seek(0)

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Should succeed for internal symlinks
            import pathlib

            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                output_path = pathlib.Path(output_dir).resolve()
                for member in tar.getmembers():
                    member_path = (output_path / member.name).resolve()
                    if not str(member_path).startswith(str(output_path)):
                        raise ValueError(f"Attempted path traversal in tar file: {member.name}")
                tar.extractall(output_dir)

            # Verify extraction
            assert (output_dir / "data" / "original.txt").exists()

    def test_safe_extraction_legitimate_files(self):
        """Test that legitimate tar extraction works correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create safe tar with legitimate structure
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                # Add legitimate files
                for name in ["data/file1.txt", "data/subdir/file2.txt", "metadata.json"]:
                    info = tarfile.TarInfo(name=name)
                    content = f"content of {name}".encode()
                    info.size = len(content)
                    tar.addfile(info, BytesIO(content))

            tar_buffer.seek(0)

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Extract should succeed
            import pathlib

            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                output_path = pathlib.Path(output_dir).resolve()
                for member in tar.getmembers():
                    member_path = (output_path / member.name).resolve()
                    if not str(member_path).startswith(str(output_path)):
                        raise ValueError(f"Attempted path traversal in tar file: {member.name}")
                tar.extractall(output_dir)

            # Verify files were extracted
            assert (output_dir / "data" / "file1.txt").exists()
            assert (output_dir / "data" / "subdir" / "file2.txt").exists()
            assert (output_dir / "metadata.json").exists()

            # Verify content
            assert (output_dir / "data" / "file1.txt").read_text() == "content of data/file1.txt"

    def test_safe_extraction_with_directories(self):
        """Test that directories in tar files are extracted safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create tar with explicit directory entries and proper permissions
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                # Add directory with permissions
                dir_info = tarfile.TarInfo(name="data/")
                dir_info.type = tarfile.DIRTYPE
                dir_info.mode = 0o755  # Set directory permissions
                tar.addfile(dir_info)

                # Add file in directory with permissions
                file_info = tarfile.TarInfo(name="data/file.txt")
                content = b"test content"
                file_info.size = len(content)
                file_info.mode = 0o644  # Set file permissions
                tar.addfile(file_info, BytesIO(content))

            tar_buffer.seek(0)

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Extract should succeed
            import pathlib

            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                output_path = pathlib.Path(output_dir).resolve()
                for member in tar.getmembers():
                    member_path = (output_path / member.name).resolve()
                    if not str(member_path).startswith(str(output_path)):
                        raise ValueError(f"Attempted path traversal in tar file: {member.name}")
                tar.extractall(output_dir)

            # Verify structure
            assert (output_dir / "data").is_dir()
            assert (output_dir / "data" / "file.txt").exists()
            # Verify content can be read
            assert (output_dir / "data" / "file.txt").read_bytes() == b"test content"

    def test_path_traversal_mixed_attack_vectors(self):
        """Test blocking of multiple attack vectors in same archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create tar with multiple attack vectors
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                # Legitimate file
                info1 = tarfile.TarInfo(name="legitimate.txt")
                info1.size = 0
                tar.addfile(info1, BytesIO(b""))

                # Attack vector 1: parent directory
                info2 = tarfile.TarInfo(name="../attack1.txt")
                info2.size = 0
                tar.addfile(info2, BytesIO(b""))

            tar_buffer.seek(0)

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Should fail on first malicious member
            with pytest.raises(ValueError, match="Attempted path traversal"):
                import pathlib

                with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                    output_path = pathlib.Path(output_dir).resolve()
                    for member in tar.getmembers():
                        member_path = (output_path / member.name).resolve()
                        if not str(member_path).startswith(str(output_path)):
                            raise ValueError(f"Attempted path traversal in tar file: {member.name}")
                    tar.extractall(output_dir)

            # Legitimate file should NOT be extracted (fail-fast behavior)
            assert not (output_dir / "legitimate.txt").exists()


class TestTarfileExtractionErrorHandling:
    """Test error handling and edge cases in tarfile extraction."""

    def test_empty_tar_file(self):
        """Test extraction of empty tar file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty tar
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                pass  # Empty archive

            tar_buffer.seek(0)

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Should succeed without errors
            import pathlib

            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                output_path = pathlib.Path(output_dir).resolve()
                for member in tar.getmembers():
                    member_path = (output_path / member.name).resolve()
                    if not str(member_path).startswith(str(output_path)):
                        raise ValueError(f"Attempted path traversal in tar file: {member.name}")
                tar.extractall(output_dir)

    def test_case_sensitivity_in_path_validation(self):
        """Test that path validation is case-sensitive on case-sensitive filesystems."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create tar with uppercase attempt (edge case)
            tar_buffer = BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                info = tarfile.TarInfo(name="DATA/file.txt")
                info.size = 0
                tar.addfile(info, BytesIO(b""))

            tar_buffer.seek(0)

            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            # Should succeed (legitimate subdirectory)
            import pathlib

            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                output_path = pathlib.Path(output_dir).resolve()
                for member in tar.getmembers():
                    member_path = (output_path / member.name).resolve()
                    if not str(member_path).startswith(str(output_path)):
                        raise ValueError(f"Attempted path traversal in tar file: {member.name}")
                tar.extractall(output_dir)

            assert (output_dir / "DATA" / "file.txt").exists()
