#!/usr/bin/env python
"""Generate performance graphs from benchmark history.

Usage:
    python scripts/benchmarks/generate_graphs.py
"""

import json
import sys
from pathlib import Path
from typing import Any

try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib not installed, skipping graph generation", file=sys.stderr)

# Paths
RESULTS_DIR = Path(__file__).parent.parent.parent / "docs" / "performance"
HISTORY_FILE = RESULTS_DIR / "benchmark-history.json"
GRAPHS_DIR = RESULTS_DIR / "graphs"


def load_history() -> dict[str, Any]:
    """Load benchmark history."""
    if not HISTORY_FILE.exists():
        print(f"❌ History file not found: {HISTORY_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(HISTORY_FILE) as f:
        return json.load(f)


def generate_execution_time_graph(history: dict[str, Any]) -> None:
    """Generate execution time vs commit graph."""
    if not MATPLOTLIB_AVAILABLE:
        return

    runs = history.get("runs", [])

    # Group by scenario
    by_scenario = {}
    for run in runs:
        scenario = run.get("scenario", "unknown")
        if scenario not in by_scenario:
            by_scenario[scenario] = {"timestamps": [], "times": []}

        by_scenario[scenario]["timestamps"].append(run.get("timestamp", ""))
        by_scenario[scenario]["times"].append(run.get("execution_time", 0.0))

    # Create plot
    plt.figure(figsize=(12, 6))

    for scenario, data in sorted(by_scenario.items())[:5]:  # Top 5 scenarios
        plt.plot(range(len(data["times"])), data["times"], marker="o", label=scenario)

    plt.xlabel("Run Number")
    plt.ylabel("Execution Time (seconds)")
    plt.title("Benchmark Execution Time Trends")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    output_path = GRAPHS_DIR / "execution_time_trends.png"
    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"✅ Generated: {output_path}")


def main():
    """Main entry point."""
    if not MATPLOTLIB_AVAILABLE:
        print("Skipping graph generation (matplotlib not available)")
        return

    # Create graphs directory
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)

    # Load history
    history = load_history()

    if not history.get("runs"):
        print("No benchmark runs in history, skipping graph generation")
        return

    # Generate graphs
    print("Generating performance graphs...")
    generate_execution_time_graph(history)

    print("\nAll graphs generated successfully!")


if __name__ == "__main__":
    main()
