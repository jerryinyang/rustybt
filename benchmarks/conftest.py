"""pytest-benchmark configuration for RustyBT benchmarks.

Configures benchmark parameters, fixtures, and result storage for
performance baseline measurements.
"""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(scope="session")
def benchmark_results_dir() -> Path:
    """Return benchmark results directory.

    Returns:
        Path to benchmarks/results directory
    """
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    return results_dir


def pytest_benchmark_update_json(
    config: Any, benchmarks: list[dict[str, Any]], output_json: dict[str, Any]
) -> None:
    """Customize benchmark JSON output format.

    Args:
        config: pytest config
        benchmarks: list of benchmark results
        output_json: output JSON structure to customize
    """
    # Add metadata
    output_json["rustybt_metadata"] = {
        "version": "1.0",
        "benchmark_type": "decimal_baseline",
        "purpose": "Epic 7 Rust optimization baseline",
    }


def pytest_configure(config: Any) -> None:
    """Configure pytest benchmark settings.

    Args:
        config: pytest config
    """
    config.addinivalue_line(
        "markers",
        "benchmark: mark test as a benchmark for performance measurement",
    )
