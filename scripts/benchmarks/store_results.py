#!/usr/bin/env python
"""Store benchmark results to history file.

Usage:
    python scripts/benchmarks/store_results.py benchmark-results.json
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Paths
RESULTS_DIR = Path(__file__).parent.parent.parent / "docs" / "performance"
HISTORY_FILE = RESULTS_DIR / "benchmark-history.json"
MAX_RUNS = 100  # Keep last 100 runs


def get_git_info() -> dict:
    """Get current Git commit info."""
    try:
        commit = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )

        branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode("utf-8")
            .strip()
        )

        return {"commit": commit, "branch": branch}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": "unknown", "branch": "unknown"}


def load_history() -> dict:
    """Load existing history or create new."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"runs": []}


def save_history(history: dict) -> None:
    """Save history to file."""
    # Ensure results directory exists
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Limit number of runs
    if len(history["runs"]) > MAX_RUNS:
        history["runs"] = history["runs"][-MAX_RUNS:]

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Store benchmark results")
    parser.add_argument("results_file", help="Path to pytest-benchmark results JSON file")

    args = parser.parse_args()

    # Load benchmark results
    results_path = Path(args.results_file)
    if not results_path.exists():
        print(f"❌ Results file not found: {results_path}", file=sys.stderr)
        sys.exit(1)

    with open(results_path) as f:
        bench_results = json.load(f)

    # Get Git info
    git_info = get_git_info()

    # Load history
    history = load_history()

    # Create new run entry
    run_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "git_commit": git_info["commit"],
        "git_branch": git_info["branch"],
        "benchmarks": bench_results.get("benchmarks", []),
    }

    # Add to history
    history["runs"].append(run_entry)

    # Save history
    save_history(history)

    print(f"✅ Stored {len(bench_results.get('benchmarks', []))} benchmark results")
    print(f"   Commit: {git_info['commit'][:8]}")
    print(f"   Branch: {git_info['branch']}")
    print(f"   Total runs in history: {len(history['runs'])}")


if __name__ == "__main__":
    main()
