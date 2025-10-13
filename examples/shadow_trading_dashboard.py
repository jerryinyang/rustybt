"""Example: Using the shadow trading alignment dashboard.

This example demonstrates how to use the AlignmentDashboard to query
alignment metrics for visualization and monitoring.
"""

import json
from datetime import timedelta

from rustybt.live.shadow import AlignmentDashboard
from rustybt.live.state_manager import StateManager


def display_signal_match_rate(dashboard: AlignmentDashboard) -> None:
    """Display signal match rate metrics."""
    print("\n=== Signal Match Rate (Last Hour) ===")

    match_rate, divergence = dashboard.get_signal_match_rate(time_window=timedelta(hours=1))

    print(f"Match Rate: {match_rate:.2%}")
    print("\nDivergence Breakdown:")
    for alignment_type, count in divergence.items():
        print(f"  {alignment_type}: {count}")


def display_execution_quality(dashboard: AlignmentDashboard) -> None:
    """Display execution quality metrics."""
    print("\n=== Execution Quality (Last Hour) ===")

    metrics = dashboard.get_execution_quality_metrics(time_window=timedelta(hours=1))

    print("Slippage:")
    print(f"  Expected: {metrics['expected_slippage_bps']:.2f} bps")
    print(f"  Actual: {metrics['actual_slippage_bps']:.2f} bps")
    print(f"  Error: {metrics['slippage_error_bps']:.2f} bps")

    print("\nFill Rate:")
    print(f"  Expected: {metrics['fill_rate_expected']:.2%}")
    print(f"  Actual: {metrics['fill_rate_actual']:.2%}")
    print(f"  Error: {metrics['fill_rate_error_pct']:.2f}%")

    print("\nCommission:")
    print(f"  Expected: ${metrics['commission_expected']:.2f}")
    print(f"  Actual: ${metrics['commission_actual']:.2f}")
    print(f"  Error: {metrics['commission_error_pct']:.2f}%")


def display_alignment_trends(dashboard: AlignmentDashboard) -> None:
    """Display alignment trends over multiple time periods."""
    print("\n=== Alignment Trends ===")

    trends = dashboard.get_alignment_trend()

    print(f"{'Period':<10} {'Match Rate':<12} {'Slippage Err':<15} {'Fill Rate Err':<15}")
    print("-" * 55)

    for period, metrics in trends.items():
        match_rate = float(metrics["signal_match_rate"]) * 100
        slippage_err = float(metrics["avg_slippage_error_bps"])
        fill_err = float(metrics["avg_fill_rate_error_pct"])

        print(f"{period:<10} {match_rate:>10.2f}%  {slippage_err:>12.2f} bps  {fill_err:>12.2f}%")


def export_dashboard_data(
    dashboard: AlignmentDashboard, filename: str = "dashboard_data.json"
) -> None:
    """Export all dashboard data to JSON file."""
    print(f"\n=== Exporting Dashboard Data to {filename} ===")

    data = dashboard.export_dashboard_json(time_window=timedelta(hours=1))

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    print("Dashboard data exported successfully")
    print(f"Timestamp: {data['timestamp']}")
    print(f"Time Window: {data['time_window_seconds']} seconds")


def main():
    """Run dashboard example."""
    print("Shadow Trading Alignment Dashboard Example")
    print("=" * 60)

    # Initialize state manager (use your actual checkpoint directory)
    state_manager = StateManager(
        checkpoint_dir=".checkpoints",
        strategy_name="my_strategy",
    )

    # Create dashboard
    dashboard = AlignmentDashboard(
        state_manager=state_manager,
        strategy_name="my_strategy",
    )

    # Display various dashboard metrics
    display_signal_match_rate(dashboard)
    display_execution_quality(dashboard)
    display_alignment_trends(dashboard)

    # Export data for external visualization
    export_dashboard_data(dashboard)

    print("\n" + "=" * 60)
    print("Dashboard query complete!")
    print("\nNOTE: This example requires an active shadow trading session")
    print("with alignment metrics in the StateManager checkpoints.")


if __name__ == "__main__":
    main()
