"""Performance and concurrency tests for BacktestArtifactManager.

Tests cover:
- Directory creation performance (<100ms requirement)
- Concurrent backtest execution
- Thread-safe ID generation under load
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from rustybt.backtest.artifact_manager import BacktestArtifactManager


class TestPerformance:
    """Test performance requirements."""

    def test_directory_creation_performance(self, tmp_path):
        """Verify directory creation completes in <100ms."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))

        # Measure directory creation time
        start_time = time.time()
        output_dir = manager.create_directory_structure()
        end_time = time.time()

        duration_ms = (end_time - start_time) * 1000

        # Verify directory created
        assert output_dir.exists()

        # Verify performance requirement: <100ms
        assert (
            duration_ms < 100
        ), f"Directory creation took {duration_ms:.2f}ms (requirement: <100ms)"

    def test_directory_creation_performance_multiple_runs(self, tmp_path):
        """Verify directory creation is consistently fast across multiple runs."""
        durations = []

        for i in range(10):
            manager = BacktestArtifactManager(base_dir=str(tmp_path))

            start_time = time.time()
            manager.create_directory_structure()
            end_time = time.time()

            duration_ms = (end_time - start_time) * 1000
            durations.append(duration_ms)

        # Verify all runs meet <100ms requirement
        for i, duration_ms in enumerate(durations):
            assert duration_ms < 100, f"Run {i + 1} took {duration_ms:.2f}ms (requirement: <100ms)"

        # Verify average is well below threshold
        avg_duration = sum(durations) / len(durations)
        assert avg_duration < 50, f"Average duration {avg_duration:.2f}ms (target: <50ms)"

    def test_id_generation_performance(self, tmp_path):
        """Verify ID generation is fast with thread-safety guarantees."""
        manager = BacktestArtifactManager(base_dir=str(tmp_path))

        # Generate 100 IDs and measure total time
        # Note: Each ID generation includes a 1ms sleep for uniqueness guarantee
        start_time = time.time()
        for _ in range(100):
            manager.generate_backtest_id()
        end_time = time.time()

        total_duration_ms = (end_time - start_time) * 1000
        avg_per_id_ms = total_duration_ms / 100

        # Should be ~1ms per ID (includes intentional 1ms sleep for uniqueness)
        assert avg_per_id_ms < 2, f"Average ID generation time: {avg_per_id_ms:.4f}ms"


class TestConcurrency:
    """Test concurrent execution scenarios."""

    def test_concurrent_id_generation_uniqueness(self, tmp_path):
        """Verify concurrent ID generation from multiple threads produces unique IDs."""
        num_threads = 20
        ids_per_thread = 10
        all_ids = []

        def generate_ids():
            """Generate multiple IDs in a thread."""
            thread_ids = []
            for _ in range(ids_per_thread):
                manager = BacktestArtifactManager(base_dir=str(tmp_path))
                thread_ids.append(manager.generate_backtest_id())
            return thread_ids

        # Run concurrent ID generation
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(generate_ids) for _ in range(num_threads)]
            for future in as_completed(futures):
                all_ids.extend(future.result())

        # Verify all IDs are unique
        total_ids = num_threads * ids_per_thread
        assert len(all_ids) == total_ids
        assert len(set(all_ids)) == total_ids, "Duplicate IDs found in concurrent generation"

    def test_concurrent_directory_creation(self, tmp_path):
        """Verify concurrent directory creation from multiple threads succeeds."""
        num_threads = 10
        output_dirs = []

        def create_directory():
            """Create directory structure in a thread."""
            manager = BacktestArtifactManager(base_dir=str(tmp_path))
            return manager.create_directory_structure()

        # Run concurrent directory creation
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_directory) for _ in range(num_threads)]
            for future in as_completed(futures):
                output_dirs.append(future.result())

        # Verify all directories created
        assert len(output_dirs) == num_threads

        # Verify all directories exist and are unique
        unique_dirs = set(str(d) for d in output_dirs)
        assert len(unique_dirs) == num_threads

        for output_dir in output_dirs:
            assert output_dir.exists()
            assert (output_dir / "results").exists()
            assert (output_dir / "code").exists()
            assert (output_dir / "metadata").exists()

    def test_concurrent_directory_creation_performance(self, tmp_path):
        """Verify concurrent directory creation meets performance requirements."""
        num_threads = 5
        durations = []

        def create_and_time():
            """Create directory and measure time."""
            manager = BacktestArtifactManager(base_dir=str(tmp_path))
            start_time = time.time()
            manager.create_directory_structure()
            end_time = time.time()
            return (end_time - start_time) * 1000

        # Run concurrent creation with timing
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_and_time) for _ in range(num_threads)]
            for future in as_completed(futures):
                durations.append(future.result())

        # Verify all meet <100ms requirement
        for i, duration_ms in enumerate(durations):
            assert (
                duration_ms < 100
            ), f"Thread {i + 1} took {duration_ms:.2f}ms (requirement: <100ms)"

    def test_high_concurrency_stress_test(self, tmp_path):
        """Stress test with high concurrency (50 threads)."""
        num_threads = 50
        results = []

        def create_backtest():
            """Create complete backtest artifact structure."""
            try:
                manager = BacktestArtifactManager(base_dir=str(tmp_path))
                output_dir = manager.create_directory_structure()
                return {"success": True, "output_dir": output_dir, "error": None}
            except Exception as e:
                return {"success": False, "output_dir": None, "error": str(e)}

        # Run high concurrency stress test
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_backtest) for _ in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())

        # Verify all succeeded
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        assert len(successes) == num_threads, f"{len(failures)} failures: {failures}"

        # Verify all directories unique
        output_dirs = [r["output_dir"] for r in successes]
        assert len(set(str(d) for d in output_dirs)) == num_threads


class TestBacktestOverhead:
    """Test backtest execution overhead."""

    @pytest.mark.benchmark
    def test_artifact_management_overhead(self, tmp_path, benchmark):
        """Benchmark directory creation overhead using pytest-benchmark."""

        def create_structure():
            manager = BacktestArtifactManager(base_dir=str(tmp_path))
            return manager.create_directory_structure()

        # Benchmark the operation
        result = benchmark(create_structure)

        # Verify it completed
        assert result.exists()

        # pytest-benchmark will automatically record and compare performance

    def test_overhead_less_than_2_percent(self, tmp_path):
        """Verify artifact management adds <2% overhead (simulated backtest)."""
        # Simulate a 5-second backtest
        simulated_backtest_duration_ms = 5000

        # Measure artifact management time
        manager = BacktestArtifactManager(base_dir=str(tmp_path))
        start_time = time.time()
        manager.create_directory_structure()
        end_time = time.time()

        artifact_duration_ms = (end_time - start_time) * 1000

        # Calculate overhead percentage
        overhead_pct = (artifact_duration_ms / simulated_backtest_duration_ms) * 100

        # Verify <2% overhead
        assert overhead_pct < 2.0, f"Overhead: {overhead_pct:.2f}% (requirement: <2%)"
