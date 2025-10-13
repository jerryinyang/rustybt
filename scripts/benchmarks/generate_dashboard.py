#!/usr/bin/env python
"""Generate static HTML dashboard from benchmark history.

This script creates a self-contained HTML dashboard with embedded graphs
and benchmark data visualization. No external dependencies required for viewing.

Usage:
    python scripts/benchmarks/generate_dashboard.py

Output:
    docs/performance/dashboard.html
"""

import base64
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib not installed, dashboard will have limited functionality")

# Paths
RESULTS_DIR = Path(__file__).parent.parent.parent / "docs" / "performance"
HISTORY_FILE = RESULTS_DIR / "benchmark-history.json"
DASHBOARD_FILE = RESULTS_DIR / "dashboard.html"


def load_history() -> dict[str, Any]:
    """Load benchmark history."""
    if not HISTORY_FILE.exists():
        return {"runs": [], "metadata": {}}

    with open(HISTORY_FILE) as f:
        return json.load(f)


def plot_to_base64(fig) -> str:
    """Convert matplotlib figure to base64-encoded PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    plt.close(fig)
    return f"data:image/png;base64,{img_base64}"


def generate_execution_time_chart(history: dict[str, Any]) -> str | None:
    """Generate execution time trends chart."""
    if not MATPLOTLIB_AVAILABLE:
        return None

    runs = history.get("runs", [])
    if not runs:
        return None

    # Group by scenario
    by_scenario = {}
    for run in runs:
        scenario = run.get("scenario", "unknown")
        if scenario not in by_scenario:
            by_scenario[scenario] = {"runs": [], "times": []}

        by_scenario[scenario]["runs"].append(len(by_scenario[scenario]["runs"]) + 1)
        by_scenario[scenario]["times"].append(run.get("execution_time", 0.0))

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot top 8 scenarios
    for scenario, data in sorted(
        by_scenario.items(), key=lambda x: len(x[1]["runs"]), reverse=True
    )[:8]:
        ax.plot(data["runs"], data["times"], marker="o", label=scenario, linewidth=2)

    ax.set_xlabel("Run Number", fontsize=12)
    ax.set_ylabel("Execution Time (seconds)", fontsize=12)
    ax.set_title("Benchmark Execution Time Trends", fontsize=14, fontweight="bold")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return plot_to_base64(fig)


def generate_scenario_comparison_chart(history: dict[str, Any]) -> str | None:
    """Generate scenario comparison bar chart (latest runs)."""
    if not MATPLOTLIB_AVAILABLE:
        return None

    runs = history.get("runs", [])
    if not runs:
        return None

    # Get latest run per scenario
    latest_by_scenario = {}
    for run in runs:
        scenario = run.get("scenario", "unknown")
        timestamp = run.get("timestamp", "")
        if scenario not in latest_by_scenario or timestamp > latest_by_scenario[scenario].get(
            "timestamp", ""
        ):
            latest_by_scenario[scenario] = run

    # Sort by execution time
    scenarios = sorted(
        latest_by_scenario.items(), key=lambda x: x[1].get("execution_time", 0.0), reverse=True
    )[:10]

    if not scenarios:
        return None

    scenario_names = [s[0] for s in scenarios]
    exec_times = [s[1].get("execution_time", 0.0) for s in scenarios]

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(scenario_names, exec_times, color="steelblue")

    # Color bars based on time (red for slow, green for fast)
    max_time = max(exec_times) if exec_times else 1
    if max_time > 0:
        for i, (bar, time) in enumerate(zip(bars, exec_times, strict=False)):
            color_intensity = time / max_time
            bar.set_color(plt.cm.RdYlGn_r(color_intensity))

    ax.set_xlabel("Execution Time (seconds)", fontsize=12)
    ax.set_title("Scenario Performance Comparison (Latest Runs)", fontsize=14, fontweight="bold")
    ax.grid(True, axis="x", alpha=0.3)

    fig.tight_layout()
    return plot_to_base64(fig)


def generate_html_dashboard(history: dict[str, Any]) -> str:
    """Generate complete HTML dashboard."""
    runs = history.get("runs", [])
    total_runs = len(runs)

    # Calculate statistics
    if runs:
        latest_run = max(runs, key=lambda x: x.get("timestamp", ""))
        latest_timestamp = latest_run.get("timestamp", "N/A")
        latest_commit = latest_run.get("git_commit", "N/A")[:8]
    else:
        latest_timestamp = "N/A"
        latest_commit = "N/A"

    unique_scenarios = len(set(r.get("scenario", "unknown") for r in runs))

    # Generate charts
    exec_time_chart = generate_execution_time_chart(history)
    comparison_chart = generate_scenario_comparison_chart(history)

    # Build runs table HTML
    runs_table_rows = []
    for run in sorted(runs, key=lambda x: x.get("timestamp", ""), reverse=True)[:20]:
        timestamp = run.get("timestamp", "N/A")
        scenario = run.get("scenario", "unknown")
        exec_time = run.get("execution_time", 0.0)
        commit = run.get("git_commit", "N/A")[:8]

        runs_table_rows.append(
            f"""
            <tr>
                <td>{timestamp}</td>
                <td><code>{scenario}</code></td>
                <td>{exec_time:.2f}s</td>
                <td><code>{commit}</code></td>
            </tr>
        """
        )

    runs_table = (
        "\n".join(runs_table_rows)
        if runs_table_rows
        else "<tr><td colspan='4'>No benchmark runs recorded</td></tr>"
    )

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustyBT Benchmark Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }}

        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }}

        .stat-card h3 {{
            color: #667eea;
            font-size: 2em;
            margin-bottom: 5px;
        }}

        .stat-card p {{
            color: #666;
            font-size: 0.9em;
        }}

        .section {{
            padding: 30px;
        }}

        .section h2 {{
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
            font-size: 1.8em;
        }}

        .chart {{
            margin: 20px 0;
            text-align: center;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
        }}

        .chart img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }}

        .no-chart {{
            padding: 40px;
            text-align: center;
            color: #999;
            font-style: italic;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        table thead {{
            background: #667eea;
            color: white;
        }}

        table th {{
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}

        table td {{
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }}

        table tbody tr:hover {{
            background: #f8f9fa;
        }}

        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}

        footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #e0e0e0;
            font-size: 0.9em;
        }}

        .warning {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}

        .warning strong {{
            color: #856404;
        }}

        @media (max-width: 768px) {{
            header h1 {{
                font-size: 1.8em;
            }}

            .stats {{
                grid-template-columns: 1fr;
            }}

            .section {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 RustyBT Benchmark Dashboard</h1>
            <p>Performance Monitoring & Regression Detection</p>
        </header>

        <div class="stats">
            <div class="stat-card">
                <h3>{total_runs}</h3>
                <p>Total Benchmark Runs</p>
            </div>
            <div class="stat-card">
                <h3>{unique_scenarios}</h3>
                <p>Unique Scenarios</p>
            </div>
            <div class="stat-card">
                <h3>{latest_commit}</h3>
                <p>Latest Commit</p>
            </div>
            <div class="stat-card">
                <h3>{latest_timestamp[:10] if latest_timestamp != "N/A" else "N/A"}</h3>
                <p>Last Updated</p>
            </div>
        </div>

        <div class="section">
            <h2>📊 Execution Time Trends</h2>
            <p>Track benchmark performance across multiple runs to identify trends and regressions.</p>
            {"<div class='chart'><img src='" + exec_time_chart + "' alt='Execution Time Trends'/></div>" if exec_time_chart else "<div class='no-chart'>No data available. Run benchmarks to generate charts.</div>"}
        </div>

        <div class="section">
            <h2>⚡ Scenario Performance Comparison</h2>
            <p>Compare latest execution times across different benchmark scenarios.</p>
            {"<div class='chart'><img src='" + comparison_chart + "' alt='Scenario Comparison'/></div>" if comparison_chart else "<div class='no-chart'>No data available. Run benchmarks to generate charts.</div>"}
        </div>

        <div class="section">
            <h2>📋 Recent Benchmark Runs</h2>
            <p>Last 20 benchmark executions with detailed metrics.</p>

            {f'<div class="warning"><strong>⚠️ Note:</strong> Only {total_runs} runs recorded. Run more benchmarks to see trends.</div>' if total_runs < 10 else ""}

            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Scenario</th>
                        <th>Execution Time</th>
                        <th>Git Commit</th>
                    </tr>
                </thead>
                <tbody>
                    {runs_table}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>ℹ️ About This Dashboard</h2>
            <p>This dashboard provides real-time visualization of RustyBT's benchmark performance. Data is sourced from <code>docs/performance/benchmark-history.json</code>.</p>

            <h3 style="margin-top: 20px; color: #667eea;">How to Use</h3>
            <ul style="margin-left: 20px; line-height: 1.8;">
                <li>Run benchmarks: <code>pytest tests/benchmarks/test_backtest_performance.py --benchmark-only</code></li>
                <li>Regenerate dashboard: <code>python scripts/benchmarks/generate_dashboard.py</code></li>
                <li>View regression alerts: <code>python scripts/benchmarks/detect_regressions.py</code></li>
                <li>Query history: <code>python scripts/benchmarks/query_history.py --summary</code></li>
            </ul>

            <h3 style="margin-top: 20px; color: #667eea;">Benchmark Scenarios</h3>
            <p style="margin-top: 10px;">The suite tests 15 scenarios across:</p>
            <ul style="margin-left: 20px; line-height: 1.8;">
                <li><strong>Frequencies:</strong> Daily, Hourly, Minute</li>
                <li><strong>Complexities:</strong> Simple (2 indicators), Medium (4 indicators), Complex (10+ indicators)</li>
                <li><strong>Portfolio Sizes:</strong> 10, 20, 50, 100, 500 assets</li>
                <li><strong>Optimizations:</strong> Python-only vs. Rust-optimized</li>
            </ul>
        </div>

        <footer>
            <p>Generated by <strong>RustyBT Benchmarking Suite</strong> | Story 7.5 | Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p style="margin-top: 5px;">For more information, see <code>docs/performance/benchmarking-suite.md</code></p>
        </footer>
    </div>
</body>
</html>
"""

    return html


def main():
    """Main entry point."""
    print("🚀 Generating RustyBT Benchmark Dashboard...")
    print(f"📂 Loading history from: {HISTORY_FILE}")

    # Load history
    history = load_history()

    total_runs = len(history.get("runs", []))
    print(f"📊 Found {total_runs} benchmark runs")

    if not MATPLOTLIB_AVAILABLE:
        print("⚠️  matplotlib not available - dashboard will be generated without charts")
        print("   Install with: pip install matplotlib")

    # Generate dashboard
    html = generate_html_dashboard(history)

    # Write to file
    DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_FILE, "w") as f:
        f.write(html)

    print(f"✅ Dashboard generated: {DASHBOARD_FILE}")
    print(f"🌐 Open in browser: file://{DASHBOARD_FILE.absolute()}")

    if total_runs < 10:
        print("\n💡 Tip: Run more benchmarks to see meaningful trends and comparisons")
        print("   Command: pytest tests/benchmarks/test_backtest_performance.py --benchmark-only")


if __name__ == "__main__":
    main()
