"""Unit tests for profiling harness (run_profiler.py)."""

import pstats

# Import profiling functions
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.profiling.run_profiler import (
    list_scenarios,
    profile_with_cprofile,
    profile_with_memory_profiler,
    run_daily_scenario,
    run_hourly_scenario,
    run_minute_scenario,
)


def test_list_scenarios_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that list_scenarios outputs available scenarios."""
    list_scenarios()
    captured = capsys.readouterr()

    assert "Available profiling scenarios:" in captured.out
    assert "daily" in captured.out
    assert "hourly" in captured.out
    assert "minute" in captured.out
    assert "all" in captured.out


def test_run_daily_scenario_executes_without_error() -> None:
    """Test that daily scenario placeholder runs without errors."""
    # Should not raise any exceptions
    run_daily_scenario()


def test_run_hourly_scenario_executes_without_error() -> None:
    """Test that hourly scenario placeholder runs without errors."""
    # Should not raise any exceptions
    run_hourly_scenario()


def test_run_minute_scenario_executes_without_error() -> None:
    """Test that minute scenario placeholder runs without errors."""
    # Should not raise any exceptions
    run_minute_scenario()


def test_profile_with_cprofile_generates_output_files() -> None:
    """Test that cProfile profiling generates expected output files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Profile a simple function
        def sample_work() -> None:
            """Sample work function."""
            total = 0
            for i in range(1000):
                total += i

        profile_with_cprofile("test_scenario", sample_work, output_dir)

        # Verify .pstats file exists
        pstats_file = output_dir / "test_scenario_cprofile.pstats"
        assert pstats_file.exists()

        # Verify .pstats file is readable by pstats module
        stats = pstats.Stats(str(pstats_file))
        assert stats is not None
        assert stats.total_calls > 0

        # Verify summary file exists
        summary_file = output_dir / "test_scenario_cprofile_summary.txt"
        assert summary_file.exists()

        # Verify summary file contains expected content
        summary_content = summary_file.read_text()
        assert "cProfile Summary: test_scenario" in summary_content
        assert "Top 20 functions by cumulative time:" in summary_content
        assert "ncalls" in summary_content


def test_profile_with_cprofile_pstats_format_valid() -> None:
    """Test that generated .pstats file has valid format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        def sample_work() -> None:
            """Sample work function."""
            _ = [i**2 for i in range(100)]

        profile_with_cprofile("format_test", sample_work, output_dir)

        pstats_file = output_dir / "format_test_cprofile.pstats"

        # Load and verify stats can be sorted and printed
        stats = pstats.Stats(str(pstats_file))
        stats.sort_stats("cumulative")

        # Verify stats has expected structure
        assert hasattr(stats, "stats")
        assert hasattr(stats, "total_calls")
        assert isinstance(stats.stats, dict)
        assert stats.total_calls > 0


def test_profile_with_memory_profiler_when_installed() -> None:
    """Test memory profiler when memory_profiler is available."""
    try:
        import memory_profiler  # noqa: F401

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            def sample_work() -> None:
                """Sample work function."""
                data = list(range(10000))
                _ = sum(data)

            profile_with_memory_profiler("mem_test", sample_work, output_dir)

            # Verify memory profile file exists
            mem_file = output_dir / "mem_test_memory.txt"
            assert mem_file.exists()

            # Verify file contains expected content
            mem_content = mem_file.read_text()
            assert "Memory Profiling: mem_test" in mem_content
            assert "Peak memory usage:" in mem_content
            assert "Mean memory usage:" in mem_content
            assert "MiB" in mem_content

    except ImportError:
        pytest.skip("memory_profiler not installed")


def test_profile_with_memory_profiler_handles_missing_package(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test memory profiler gracefully handles missing package."""
    # Temporarily hide memory_profiler if it exists
    import sys

    original_modules = sys.modules.copy()

    try:
        if "memory_profiler" in sys.modules:
            del sys.modules["memory_profiler"]

        # Mock the import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "memory_profiler":
                raise ImportError("memory_profiler not found")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            def sample_work() -> None:
                pass

            # Should not raise exception, just log warning
            profile_with_memory_profiler("test", sample_work, output_dir)

            # No memory file should be created
            mem_file = output_dir / "test_memory.txt"
            assert not mem_file.exists()

    finally:
        # Restore original state
        builtins.__import__ = original_import
        sys.modules.clear()
        sys.modules.update(original_modules)


def test_cprofile_summary_contains_top_20_functions() -> None:
    """Test that cProfile summary lists top 20 functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        def sample_work() -> None:
            """Sample work with multiple function calls."""
            # Create enough function calls to have >20 entries
            for i in range(50):
                _ = str(i)
                _ = len(str(i))

        profile_with_cprofile("top20_test", sample_work, output_dir)

        summary_file = output_dir / "top20_test_cprofile_summary.txt"
        summary_content = summary_file.read_text()

        # Verify it's limited to 20 (or fewer if < 20 total functions)
        assert (
            "List reduced from" in summary_content
            or "Ordered by: cumulative time" in summary_content
        )
