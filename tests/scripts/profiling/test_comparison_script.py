"""Unit tests for profile comparison script (compare_profiles.py)."""

# Import comparison functions
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.profiling.compare_profiles import (
    calculate_overall_runtime_delta,
    compare_function_stats,
    extract_top_functions,
    generate_comparison_report,
    load_profile_stats,
)


def create_sample_profile(output_path: Path, iterations: int = 100) -> None:
    """Create a sample .pstats file for testing."""
    import cProfile

    def sample_function() -> int:
        """Sample function to profile."""
        total = 0
        for i in range(iterations):
            total += i**2
        return total

    profiler = cProfile.Profile()
    profiler.enable()
    sample_function()
    profiler.disable()
    profiler.dump_stats(str(output_path))


def test_load_profile_stats_success() -> None:
    """Test loading valid profile stats file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_path = Path(tmpdir) / "test.pstats"
        create_sample_profile(profile_path)

        stats = load_profile_stats(profile_path)
        assert stats is not None
        assert hasattr(stats, "stats")
        assert hasattr(stats, "total_calls")


def test_load_profile_stats_file_not_found() -> None:
    """Test loading non-existent profile file raises error."""
    with pytest.raises(FileNotFoundError):
        load_profile_stats(Path("/nonexistent/path/to/profile.pstats"))


def test_extract_top_functions_returns_correct_format() -> None:
    """Test extract_top_functions returns list of tuples with correct structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_path = Path(tmpdir) / "test.pstats"
        create_sample_profile(profile_path)

        stats = load_profile_stats(profile_path)
        top_funcs = extract_top_functions(stats, n=10)

        assert isinstance(top_funcs, list)
        assert len(top_funcs) <= 10

        # Check structure of returned tuples
        if len(top_funcs) > 0:
            first_func = top_funcs[0]
            assert isinstance(first_func, tuple)
            assert len(first_func) == 4  # (name, cumtime, ncalls, percall)

            func_name, cumtime, ncalls, percall = first_func
            assert isinstance(func_name, str)
            assert isinstance(cumtime, float)
            assert isinstance(ncalls, int)
            assert isinstance(percall, float)


def test_extract_top_functions_sorted_by_cumulative_time() -> None:
    """Test that extracted functions are sorted by cumulative time."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_path = Path(tmpdir) / "test.pstats"
        create_sample_profile(profile_path, iterations=1000)

        stats = load_profile_stats(profile_path)
        top_funcs = extract_top_functions(stats, n=20)

        # Verify sorting (cumulative time is index 1)
        cumtimes = [func[1] for func in top_funcs]
        assert cumtimes == sorted(cumtimes, reverse=True)


def test_compare_function_stats_calculates_deltas() -> None:
    """Test function stats comparison calculates correct deltas."""
    before_stats = [
        ("func1", 1.0, 100, 0.01),
        ("func2", 0.5, 50, 0.01),
    ]

    after_stats = [
        ("func1", 0.8, 100, 0.008),  # Improved
        ("func2", 0.6, 50, 0.012),  # Regressed
    ]

    comparisons = compare_function_stats(before_stats, after_stats)

    assert "func1" in comparisons
    assert "func2" in comparisons

    # Check func1 (improvement)
    func1_comp = comparisons["func1"]
    assert func1_comp["before_cumtime"] == 1.0
    assert func1_comp["after_cumtime"] == 0.8
    assert abs(func1_comp["cumtime_delta"] - (-0.2)) < 1e-10  # Floating point comparison
    assert func1_comp["cumtime_pct"] < 0  # Negative percentage = improvement

    # Check func2 (regression)
    func2_comp = comparisons["func2"]
    assert func2_comp["before_cumtime"] == 0.5
    assert func2_comp["after_cumtime"] == 0.6
    assert abs(func2_comp["cumtime_delta"] - 0.1) < 1e-10  # Floating point comparison
    assert func2_comp["cumtime_pct"] > 0  # Positive percentage = regression


def test_compare_function_stats_handles_new_functions() -> None:
    """Test comparison handles functions that appear only in after stats."""
    before_stats = [("func1", 1.0, 100, 0.01)]
    after_stats = [
        ("func1", 0.9, 100, 0.009),
        ("func2", 0.5, 50, 0.01),  # New function
    ]

    comparisons = compare_function_stats(before_stats, after_stats)

    assert "func2" in comparisons
    assert comparisons["func2"]["before_cumtime"] == 0
    assert comparisons["func2"]["after_cumtime"] == 0.5


def test_compare_function_stats_handles_removed_functions() -> None:
    """Test comparison handles functions that disappear in after stats."""
    before_stats = [
        ("func1", 1.0, 100, 0.01),
        ("func2", 0.5, 50, 0.01),
    ]
    after_stats = [("func1", 0.9, 100, 0.009)]  # func2 removed

    comparisons = compare_function_stats(before_stats, after_stats)

    assert "func2" in comparisons
    assert comparisons["func2"]["before_cumtime"] == 0.5
    assert comparisons["func2"]["after_cumtime"] == 0


def test_calculate_overall_runtime_delta_improvement() -> None:
    """Test runtime delta calculation for improvement case."""
    before_total = 10.0
    after_total = 8.0

    delta_sec, delta_pct = calculate_overall_runtime_delta(before_total, after_total)

    assert delta_sec == -2.0
    assert delta_pct == -20.0  # 20% improvement


def test_calculate_overall_runtime_delta_regression() -> None:
    """Test runtime delta calculation for regression case."""
    before_total = 10.0
    after_total = 12.0

    delta_sec, delta_pct = calculate_overall_runtime_delta(before_total, after_total)

    assert delta_sec == 2.0
    assert delta_pct == 20.0  # 20% regression


def test_calculate_overall_runtime_delta_zero_baseline() -> None:
    """Test runtime delta calculation handles zero baseline gracefully."""
    before_total = 0.0
    after_total = 5.0

    delta_sec, delta_pct = calculate_overall_runtime_delta(before_total, after_total)

    assert delta_sec == 5.0
    assert delta_pct == 0  # Division by zero handled


def test_generate_comparison_report_creates_markdown() -> None:
    """Test that comparison report generates valid markdown file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create before and after directories with sample profiles
        before_dir = tmpdir_path / "before"
        after_dir = tmpdir_path / "after"
        before_dir.mkdir()
        after_dir.mkdir()

        create_sample_profile(before_dir / "test_cprofile.pstats", iterations=1000)
        create_sample_profile(after_dir / "test_cprofile.pstats", iterations=500)

        output_file = tmpdir_path / "comparison.md"

        generate_comparison_report(before_dir, after_dir, "test", output_file)

        assert output_file.exists()

        # Verify markdown content
        content = output_file.read_text()
        assert "# Profile Comparison Report: test" in content
        assert "## Overall Runtime Change" in content
        assert "## Top Improvements (Reduced Time)" in content
        assert "## Top Regressions (Increased Time)" in content
        assert "Before:" in content
        assert "After:" in content


def test_generate_comparison_report_handles_missing_before_file(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test comparison report handles missing before profile gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        before_dir = tmpdir_path / "before"
        after_dir = tmpdir_path / "after"
        before_dir.mkdir()
        after_dir.mkdir()

        # Only create after profile
        create_sample_profile(after_dir / "test_cprofile.pstats")

        output_file = tmpdir_path / "comparison.md"

        # Should log warning but not crash
        generate_comparison_report(before_dir, after_dir, "test", output_file)

        # Output file should not be created if before is missing
        assert not output_file.exists()


def test_generate_comparison_report_handles_missing_after_file(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test comparison report handles missing after profile gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        before_dir = tmpdir_path / "before"
        after_dir = tmpdir_path / "after"
        before_dir.mkdir()
        after_dir.mkdir()

        # Only create before profile
        create_sample_profile(before_dir / "test_cprofile.pstats")

        output_file = tmpdir_path / "comparison.md"

        # Should log warning but not crash
        generate_comparison_report(before_dir, after_dir, "test", output_file)

        # Output file should not be created if after is missing
        assert not output_file.exists()


def test_comparison_report_shows_speedup_indicator() -> None:
    """Test that comparison report indicates speedup vs slowdown correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        before_dir = tmpdir_path / "before"
        after_dir = tmpdir_path / "after"
        before_dir.mkdir()
        after_dir.mkdir()

        # Create profiles where after is faster
        create_sample_profile(before_dir / "test_cprofile.pstats", iterations=1000)
        create_sample_profile(after_dir / "test_cprofile.pstats", iterations=500)

        output_file = tmpdir_path / "comparison.md"
        generate_comparison_report(before_dir, after_dir, "test", output_file)

        content = output_file.read_text()

        # Should show speedup indicator (exact format may vary)
        # Look for negative delta or speedup indication
        assert "Delta:" in content
        assert "%" in content
